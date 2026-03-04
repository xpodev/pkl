# Subplugin SP1 - Child plugin of A

from pkl import get_current_plugin

current = get_current_plugin()
if current:
    print(f"Subplugin SP1 loaded! Current plugin: {current.name}")
    if current.parent:
        print(f"Parent plugin: {current.parent.name}")
