# PKL

`pkl` is a Python package that implements a plugin hosting capability.


It works like a small OS. Each plugin is like a process with its own resources.
Resources can include:
* Event handlers
* Routes (for HTTP servers)
* Async workers
* Threads
* Loggers
* Plugins

The idea is that the `pkl` library provides utilities for plugins to create these resources.
The system keeps track of which resources are created by which plugin.
When a plugin is disabled, all of its resources should be released (and removed).

The system should also support async execution. And it also needs to support knowing which
plugin is currently executed.

For security, the system should also support protected resources.
For example, a protected event can only be subscribed to by the same plugin that defined the
event. This is done by the system via the current plugin.
When the system runs by itself (similar to software interrupts), there's no current plugin.

Plugins can also define API. In some cases, plugin API calls should set the plugin that provides the API
as the current plugin. Such functions can be marked by a special decorator to tell the system that when
this function is executed, it should update the current plugin.

The library should have full typing support.

The library should also support hooks for when resources are registered.

Here is an example:
```py
# a/plugin.py - plugin.py is the entrypoint

from pkl import event

@event() # protected=False is the default
def my_event(user: User):
    # code here runs before handlers
    yield
    # code here runs after handlers
```

```py
# a/__init__.py

from pkl import syscall, get_current_plugin, set_timeout, load_plugin

@syscall
def my_api():
    print(get_current_plugin().name) # should always be 'a' since this is a context preserved API

def my_other_api():
    print(get_current_plugin().name) # whatever plugin called this.


def delayed_entry():
    this = get_current_plugin()
    child = load_plugin(path=this.path / "subplugins" / "sp1") # can also load by name. path to dir
    child.enable() # here child is a child plugin. is disabled when parent is disabled and parent can disable it

    load_plugin(path=this.path / "subplugins" / "sp2").enable(detach=True) # start as a separate plugin. can't disable now

set_timeout(delayed_entry, 5)
```


```py
# b/plugin.py

from pkl import set_interval, get_current_plugin, log

# this should have a custom importer since this doesn't actually match the directory structure of `pkl`
from pkl.plugins import a


a.my_api()

set_interval(a.my_other_api, 10)

log.info("Plugin B is disabling...") # should show with plugin name
get_current_plugin().disable() # should be ok. same plugin can disable itself.
log.info("Plugin B is disabled!") # should not show since plugin is disabled.
```

## Plugins

The plugin system needs to have multiple configurable systems:
* Plugin Metadata Loader
* Plugin Loader
* Resource Manager

Plugins metadata loader is responsible for loading metadata given the plugin location (can
be path, name, URL, whatever).
The library provides loaders from manifest file.

Plugin loader is responsible for executing the plugin entry point. The entrypoint is defined
by the metadata loader.
The library provides a default loader that uses import lib.

The resource manager is responsible for managing resource.


## Startup

Plugins can declare dependencies. The dependencies are part of the metadata.
The system runs plugins according to dependency order. If a dependency fails to load,
all dependants are cancelled (the system should keep track of which plugin is running and if
not then why it's not running).

When running a plugin, any unhandled execption that's raised is catched and is set as the 
reason for error. Dependant plugins can then show which plugin they need that is not running
or is not present.

## Plugin hooks

The system should provide a hook when 'context switching'. This is to allow things
like metrics and debug utilities.
Hooks for:
* context switch
* plugin enable(d)
* plugin disable(d)

## Async

The system should utilize context variables in order to support the `get_current_plugin()` function in `async` applications.

```py
# a/__init__.py

async def my_api():
    # current plugin is whichever called this function

@syscall
async def my_other_api():
    # current plugin is the plugin that defines this function

@get("/my_test_route")
async def my_test_route():
    # current plugin is the plugin the defines this function
```

## Execution

Users should be able to define custom resources. For example, the library does not 
provide routes as a resource. Instead, users can define their own resource (Route) and
this resource should be able to use the `set_current_plugin` function.

Important note: the `set_current_plugin` is only usable when the current plugin is `None`.
This can be done by applying the `syscall` decorator outside of any plugin execution. This
means that the `route` decorator should be decorated with the `syscall` decorator.


## Logging

A logger is a resource. The exact log formatting can be configured by the system (not by
each plugin).


## Plugin Imports

The `pkl.plugins` is not a real module. It should be injected into the `sys.modules` dict.
This object allows arbitrary name lookup and should result with the relevant plugin.

Note that only plugins that define `__init__.py` are eligible to that (might change in the future).


## Events

Plugins can define their own events. Events can only be invoked by the same plugin that
defined them.

Subscribing to an event can be done via the `+=` and `-=` operators, or by `subscribe` and `unsubscribe`.


## Resource sharing

Since the plugins run Python, technically all resources are shared. 


## Plugin Host

A plugin host should not be a singleton. It should be an instance.

In order to make things easier for users, we can provide a `set_default_host` which is
used when using the library API.

Otherwise you'd have to do `host.get_current_plugin()`.
