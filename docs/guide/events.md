# Events

`pkl.events.Event` is a resource. Its owner is whoever created it: a plugin, or the host when no plugin is executing.

```python
class Event(events.Event[Params], RuntimeResource): ...     # bound to a lifetime, see Tracking

@Event
def user_joined(name: str) -> None: ...

user_joined.subscribe(handler)       # or @user_joined.on, or user_joined += handler
user_joined("Alice")                 # only the owner may invoke
```

## Rules

- **Invoking** is for the owner only: a plugin-owned event can only be invoked while that plugin executes; a host-owned
  event only from the host. Otherwise `EventPermissionError`.
- **Subscribing** is open to everyone, unless the event is `protected=True`: then only the owner may subscribe.
- A subscription is a `Callback` created *as whoever called `subscribe`*, so its handler runs **as its subscriber** (as the
  host for host subscriptions) wherever and by whomever the event is invoked, and the invoker's plugin is restored after.
  An API that is not a `syscall` runs as its caller, so a subscription made inside it still belongs to the caller.
- A subscription is a resource **of the subscriber**: releasing the subscriber's lifetime removes its handlers.
  Releasing the event drops all subscriptions. A released event raises `EventReleasedError`.

## Before / after

A generator function runs code before and after the handlers. Ending before the `yield` cancels the invocation.

```python
@Event
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
