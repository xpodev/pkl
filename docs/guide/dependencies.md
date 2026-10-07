# Dependencies

pkl does not know what a plugin dependency *is* (a manifest entry, an import, a call). It only knows how to model the
consequence: **if `B` depends on `A`, then `B` is one of `A`'s resources.** Release `A` and `B` is released with it, and
so is everything that depends on `B`.

```python
from pkl.dependencies import depends_on, require

disabled = ResourceRegistry[AppPlugin]()

depends_on(disabled, dependant=api, dependency=database)       # declared by the host...

with plugins.executing(dashboard):
    require(tracker, api)                                      # ...or by the dependant itself

disabled.release(api)        # releases dashboard, then api
disabled.release(database)   # releases database (api is already gone)
```

## It follows a lifetime

A dependency is declared **in a registry**, and holds only in that lifetime. Declare it in the "disable" registry and
disabling `A` disables its dependants; declare it in the "uninstall" registry and uninstalling `A` uninstalls them. The
same two plugins can depend on each other in one lifetime and not in another.

## Order

Registries release newest first, so a dependant (declared after the dependency's own resources were created) is released
before them: dependants are torn down before the dependency's earlier resources, and a chain `C -> B -> A` releases in the
order `C`, `B`, `A`. Declare a dependency as soon as the dependant is loaded.

## Details

- **Releasing the dependant alone** does not release the dependency, and leaves nothing behind in it, so repeatedly
  enabling and disabling a dependant does not accumulate records.
- **Cycles** terminate: each plugin is released at most once.
- **Several dependencies** (diamonds) are fine: a plugin is released once, when the first of its dependencies goes.
- **Errors** in a dependant are collected like any other: the rest is still released, and the failure surfaces as a
  (nested) `ExceptionGroup` from the release that started it.
- `depends_on` returns a `Dependency`; `dependency.unlink()` removes the relation without releasing anyone.
- A plugin cannot depend on itself (`ValueError`).
