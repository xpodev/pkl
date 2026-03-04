"""Event system for plugins."""

from __future__ import annotations

import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    List,
    Optional,
    TypeVar,
)

from .context import plugin_context
from .resource import Resource

if TYPE_CHECKING:
    from .plugin import Plugin
    from .host import PluginHost

# ParamSpec is available in Python 3.10+
if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    try:
        from typing_extensions import ParamSpec
    except ImportError:
        ParamSpec = None  # type: ignore

__all__ = ["Event", "event", "EventHandler", "EventSubscription", "HostEvent", "EventBase"]

T = TypeVar("T")
if ParamSpec is not None:
    P = ParamSpec("P")
EventHandler = Callable[..., Any]


class EventBase:
    """Base class for events providing common subscription functionality."""

    def subscribe(self, handler: EventHandler) -> None:
        """Subscribe a handler to this event. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement subscribe()")

    def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe a handler from this event. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement unsubscribe()")

    def on(self, handler: EventHandler) -> EventHandler:
        """Decorator to subscribe a handler to this event.
        
        Args:
            handler: The handler function to subscribe.
            
        Returns:
            The handler function (unchanged).
            
        Example:
            @my_event.on
            def my_handler(data: str):
                print(f"Received: {data}")
        """
        self.subscribe(handler)
        return handler

    def __iadd__(self, handler: EventHandler) -> "EventBase":
        """Subscribe using += operator."""
        self.subscribe(handler)
        return self

    def __isub__(self, handler: EventHandler) -> "EventBase":
        """Unsubscribe using -= operator."""
        self.unsubscribe(handler)
        return self


class EventSubscription(Resource):
    """A resource representing a subscription to an event.
    
    When the subscribing plugin is disabled, the subscription is automatically removed.
    """

    def __init__(self, plugin: "Plugin", event: "Event", handler: EventHandler) -> None:
        """Initialize the event subscription.
        
        Args:
            plugin: The plugin that subscribed to the event.
            event: The event being subscribed to.
            handler: The handler function.
        """
        super().__init__(plugin)
        self.event = event
        self.handler = handler

    def _cleanup(self) -> None:
        """Remove the handler from the event."""
        self.event._remove_handler(self)


class HostEvent(EventBase):
    """An event provided by the plugin host.
    
    Host events are system-level events that any plugin can subscribe to.
    They don't have a plugin owner and live as long as the host.
    """

    def __init__(
        self,
        host: "PluginHost",
        name: str,
        protected: bool = False,
        generator: Optional[Callable[..., Generator[None, None, None]]] = None,
    ) -> None:
        """Initialize the host event.

        Args:
            host: The plugin host that owns this event.
            name: The event name.
            protected: If True, only the host (outside plugin context) can invoke this event.
            generator: The generator function for custom event behavior (optional).
        """
        self.host = host
        self.name = name
        self.protected = protected
        self.generator = generator
        self._subscriptions: List[EventSubscription] = []

    def subscribe(self, handler: EventHandler) -> None:
        """Subscribe to this host event.

        Args:
            handler: The handler function to call when the event is triggered.

        Raises:
            RuntimeError: If called outside of plugin context.
        """
        current = self.host.get_current_plugin()
        if current is None:
            raise RuntimeError("Cannot subscribe to host events outside of plugin context")

        # Create a subscription resource that will auto-cleanup when the plugin is disabled
        subscription = EventSubscription(current, self, handler)  # type: ignore
        self._subscriptions.append(subscription)
        current.host.resource_manager.register(subscription)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe from this host event.

        Args:
            handler: The handler to remove.
        """
        current = self.host.get_current_plugin()
        if current is None:
            return

        # Find and disable the subscription
        for subscription in self._subscriptions[:]:
            if subscription.plugin == current and subscription.handler == handler:
                subscription.disable()
                break
    
    def _remove_handler(self, subscription: EventSubscription) -> None:
        """Remove a handler subscription (called by EventSubscription._cleanup).
        
        Args:
            subscription: The subscription to remove.
        """
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Invoke the host event.

        Args:
            *args: Positional arguments to pass to handlers.
            **kwargs: Keyword arguments to pass to handlers.

        Raises:
            RuntimeError: If the event is protected and invoked from within a plugin.
        """
        # If protected, only allow invocation from outside plugin context (host code)
        if self.protected:
            current = self.host.get_current_plugin()
            if current is not None:
                raise RuntimeError(
                    f"Host event {self.name} is protected and can only be invoked by the host"
                )

        if self.generator is not None:
            # Use the generator pattern
            gen = self.generator(*args, **kwargs)
            try:
                # Run code before handlers
                next(gen)
            except StopIteration:
                return

            # Call handlers
            self._call_handlers(*args, **kwargs)

            try:
                # Run code after handlers
                next(gen)
            except StopIteration:
                pass
        else:
            # Just call handlers
            self._call_handlers(*args, **kwargs)

    def _call_handlers(self, *args: Any, **kwargs: Any) -> None:
        """Call all registered handlers."""
        for subscription in self._subscriptions[:]:
            with plugin_context(self.host, subscription.plugin):
                subscription.handler(*args, **kwargs)


class Event(EventBase, Resource):
    """An event that plugins can subscribe to.
    
    Events can only be invoked by the plugin that owns them. Other plugins
    can subscribe to events but must access them through the owning plugin's API.
    """

    def __init__(
        self,
        plugin: "Plugin",
        name: str,
        protected: bool = False,
        generator: Optional[Callable[..., Generator[None, None, None]]] = None,
    ) -> None:
        """Initialize the event.

        Args:
            plugin: The plugin that owns this event.
            name: The event name.
            protected: If True, only the owning plugin can subscribe to this event.
            generator: The generator function for custom event behavior (optional).
        """
        super().__init__(plugin)
        self.name = name
        self.protected = protected
        self.generator = generator
        self._subscriptions: List[EventSubscription] = []

    def subscribe(self, handler: EventHandler) -> None:
        """Subscribe to this event.

        Args:
            handler: The handler function to call when the event is triggered.

        Raises:
            RuntimeError: If the event is protected and called from wrong plugin.
        """
        current = self.plugin.host.get_current_plugin()
        if current is None:
            raise RuntimeError("Cannot subscribe to event outside of plugin context")

        if self.protected and current != self.plugin:
            raise RuntimeError(
                f"Event {self.name} is protected and can only be subscribed to by {self.plugin.name}"
            )

        # Create a subscription resource that will auto-cleanup when the plugin is disabled
        subscription = EventSubscription(current, self, handler)
        self._subscriptions.append(subscription)
        current.host.resource_manager.register(subscription)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Unsubscribe from this event.

        Args:
            handler: The handler to remove.
        """
        current = self.plugin.host.get_current_plugin()
        if current is None:
            return

        # Find and disable the subscription
        for subscription in self._subscriptions[:]:
            if subscription.plugin == current and subscription.handler == handler:
                subscription.disable()
                break
    
    def _remove_handler(self, subscription: EventSubscription) -> None:
        """Remove a handler subscription (called by EventSubscription._cleanup).
        
        Args:
            subscription: The subscription to remove.
        """
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Invoke the event.

        Args:
            *args: Positional arguments to pass to handlers.
            **kwargs: Keyword arguments to pass to handlers.

        Raises:
            RuntimeError: If called from a plugin other than the owner.
        """
        current = self.plugin.host.get_current_plugin()

        # Only the owning plugin can invoke its events
        if current != self.plugin:
            raise RuntimeError(
                f"Event {self.name} can only be invoked by {self.plugin.name}"
            )

        if self.generator is not None:
            # Use the generator pattern
            gen = self.generator(*args, **kwargs)
            try:
                # Run code before handlers
                next(gen)
            except StopIteration:
                return

            # Call handlers
            self._call_handlers(*args, **kwargs)

            try:
                # Run code after handlers
                next(gen)
            except StopIteration:
                pass
        else:
            # Just call handlers
            self._call_handlers(*args, **kwargs)

    def _call_handlers(self, *args: Any, **kwargs: Any) -> None:
        """Call all registered handlers."""
        # No need to check if plugin is enabled - disabled plugins' subscriptions
        # are automatically removed via EventSubscription cleanup
        for subscription in self._subscriptions[:]:
            with plugin_context(self.plugin.host, subscription.plugin):
                subscription.handler(*args, **kwargs)

    def _cleanup(self) -> None:
        """Clean up the event."""
        # Clear subscriptions list (individual subscriptions are cleaned up separately)
        self._subscriptions.clear()


def event(protected: bool = False) -> Callable[[Callable], Event]:
    """Decorator to create an event.
    
    Automatically detects whether to create a plugin event or host event based on context:
    - If called within plugin code: creates a plugin event
    - If called outside plugin context: creates a host event

    Args:
        protected: If True, only the defining plugin can subscribe to this event (plugin events)
                   or only the host can invoke it (host events).

    Returns:
        A decorator that creates an Event or HostEvent.

    Example:
        # Plugin event with before/after behavior:
        @event()
        def my_event(user: User):
            # code before handlers
            yield
            # code after handlers
        
        # Host event (defined outside plugin context):
        @event()
        def system_message(message: str):
            print(f"[SYSTEM] {message}")
            yield
        
        # Protected host event (only host can invoke):
        @event(protected=True)
        def admin_event(data: str):
            pass
    """

    def decorator(func: Callable) -> Event:
        # Import here to avoid circular dependency
        from . import get_default_host
        
        host_obj = get_default_host()

        # Check if function is a generator
        import inspect
        is_generator = inspect.isgeneratorfunction(func)

        # Automatically detect context: if no current plugin, it's a host event
        current = host_obj.get_current_plugin()
        
        if current is None:
            # Create a host-level event
            ev = HostEvent(
                host=host_obj,
                name=func.__name__,
                protected=protected,
                generator=func if is_generator else None,
            )
            
            # Store it on the host for later access
            host_obj._events[func.__name__] = ev
            
            return ev  # type: ignore
        else:
            # Create a plugin event
            ev = Event(
                plugin=current,
                name=func.__name__,
                protected=protected,
                generator=func if is_generator else None,
            )

            # Register the event as a resource
            current.host.resource_manager.register(ev)

            return ev  # type: ignore

    return decorator
