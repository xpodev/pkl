# Events

`pkl.events.Event` is a resource. Its owner is whoever created it: a plugin, or the host when no plugin is executing.

Events are created with a decorator **function** that you build once, in your SDK, for your lifetime:

```python
# sdk.py
event = events.event_decorator(runtime_tracker)

# a plugin
@event
def user_joined(name: str) -> None: ...

@event(protected=False)              # anyone may invoke this one
def ping() -> None: ...

user_joined.subscribe(handler)       # or @user_joined.on, or user_joined += handler
user_joined("Alice")                 # protected by default: only the owner may invoke
```

`event_decorator` takes the `ResourceTracker` the events belong to (or an `Event` subclass already bound to one). The
decorated function only defines the event's signature and name.

## Rules

- **Invoking** is for the owner only (`protected=True`, the default): a plugin-owned event can only be invoked while that
  plugin executes; a host-owned event only from the host. Otherwise `EventPermissionError`. `protected=False` lets
  anyone invoke the event.
- **Subscribing** is always open. There is no subscription control: an event that must not be subscribed to should not
  be part of the plugin's public API.
- A subscription is a `Callback` created *as whoever called `subscribe`*, so its handler runs **as its subscriber** (as the
  host for host subscriptions) wherever and by whomever the event is invoked, and the invoker's plugin is restored after.
  An API that is not a `syscall` runs as its caller, so a subscription made inside it still belongs to the caller.
- A subscription is a resource **of the subscriber**: releasing the subscriber's lifetime removes its handlers.
  Releasing the event drops all subscriptions. A released event raises `EventReleasedError`.

## Before / after

A generator function runs code before and after the handlers, as the event's owner (also when an unprotected event is
invoked by someone else). Ending before the `yield` cancels the invocation.

```python
@event
def user_joined(name: str) -> Generator[None, None, None]:
    print("before")
    yield
    print("after")
```

## Async

`await event.emit(...)` is `event(...)` for handlers that return awaitables: handlers run one after the other, each as
its subscriber, also across awaits.

## Typing

`Event` is generic over its signature (`ParamSpec`): `subscribe` only accepts compatible handlers and the call checks
its arguments.
