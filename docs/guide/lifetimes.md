# Lifetimes

pkl has no notion of enabled, disabled or installed. A lifetime is a `ResourceRegistry`: the resources of a plugin
that can be released on demand. *When* you release them is what defines the lifetime.

```python
runtime = ResourceRegistry[AppPlugin]()      # dies on disable
persistent = ResourceRegistry[AppPlugin]()   # dies on uninstall

def disable(plugin: AppPlugin) -> None:
    runtime.release(plugin)

def uninstall(plugin: AppPlugin) -> None:
    disable(plugin)
    persistent.release(plugin)
```

Call `release` on a timer and it is a "random" lifetime. Create a registry per request, per session, per zone: they are
cheap and independent. Which registry a resource goes to is decided by the base class it derives from, see
[Tracking](tracking.md).

Ordering is yours: pkl releases newest first within a plugin and does not know that one plugin depends on another.
Release plugins in the order your application needs, or use `release_all()` for newest first.
