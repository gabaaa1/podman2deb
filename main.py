#!/usr/bin/env python3

if __name__ == "__main__":
    import importlib
    import os
    import sys
    import typing
    direpa_script=os.path.dirname(os.path.realpath(__file__))
    direpa_script_parent=os.path.dirname(direpa_script)
    module_name=os.path.basename(direpa_script)
    sys.path.insert(0, direpa_script_parent)
    if typing.TYPE_CHECKING:
        import __init__ as package #type:ignore
    pkg:"package" = importlib.import_module(module_name) #type:ignore
    del sys.path[0]

    # def seed(pkg_major, direpas_configuration=dict(), fun_auto_migrate=None):
        # fun_auto_migrate() # type:ignore
    # etconf=pkg.Etconf(enable_dev_conf=False, tree=dict( files=dict({ "settings.json": dict() })), seed=seed)
    # args=pkg.Nargs(
    #     options_file="config/options.yaml", 
    #     # path_etc=etconf.direpa_configuration,
    # ).get_args()
