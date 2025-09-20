#!/usr/bin/env python3

from genericpath import exists
import yaml


if __name__ == "__main__":
    from pprint import pprint
    import json
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
        from .dev.models import Debinfo
    pkg:"package" = importlib.import_module(module_name) #type:ignore
    del sys.path[0]

    # def seed(pkg_major, direpas_configuration=dict(), fun_auto_migrate=None):
        # fun_auto_migrate() # type:ignore
    # etconf=pkg.Etconf(enable_dev_conf=False, tree=dict( files=dict({ "settings.json": dict() })), seed=seed)
    args=pkg.Nargs(
        options_file="config/options.yaml", 
        # path_etc=etconf.direpa_configuration,
    ).get_args()

    filenpa_info=os.path.join(direpa_script, "config", "debinfo.yaml")
    direpa_sources=os.path.join(direpa_script, "sources")
    direpa_builds=os.path.join(direpa_script, "builds")
    direpa_pkg=os.path.join(direpa_script, "pkg")

    os.makedirs(direpa_sources, exist_ok=True)
    direpa_assets=os.path.join(direpa_script, "assets")
    os.makedirs(direpa_assets, exist_ok=True)
    info:"Debinfo"
    with open(filenpa_info, "r") as f:
        info=pkg.Debinfo(**yaml.safe_load(f))
        info.repos=[pkg.Repo(**r) for r in info.repos] #type:ignore

    # info:Debinfo,
    # direpa_sources:str,
    # direpa_assets:str,
    # direpa_pkg:str,
    # direpa_builds:str,
    # podman_tag:str|None=None,
    # update:bool=True,
    # clean:bool=True,

    sudo=pkg.Sudo(environ="debkey")

    if args.update._here:
        pkg.update(
            direpa_sources=direpa_sources,
            info=info,    
        )

    if args.clean._here:
        pkg.clean(
            direpa_sources=direpa_sources,
            direpa_pkg=direpa_pkg,
            direpa_assets=direpa_assets,
            info=info,    
            sudo=sudo,
        )

    if args.list_tags._here:
        repo=[r for r in info.repos if r.name == pkg.RepoName.PODMAN][0]
        print(json.dumps(pkg.list_tags(
            direpa_sources, 
            repo, 
        ), indent=4))

    if args.build_info._here:
        pkg.build_info(
            info,
            direpa_sources=direpa_sources,
            podman_tag=args.build_info.tag._value,
        )

    if args.build._here:
        pkg.build(
            info,
            direpa_sources=direpa_sources,
            direpa_assets=direpa_assets,
            direpa_pkg=direpa_pkg,
            direpa_builds=direpa_builds,
            sudo=sudo,
            podman_tag=args.build.tag._value,
        )

