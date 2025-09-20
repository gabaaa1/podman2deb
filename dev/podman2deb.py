#!/usr/bin/env python3
from pprint import pprint
import hashlib
import requests
import tarfile
import json
import os
import sys
from datetime import datetime
import subprocess
import tempfile
import shutil
from dataclasses import asdict
import platform
from contextlib import contextmanager

from src.gpkgs.semver.dev.semver import NotSemanticVersion


from .install_deps import add_conf, install_aardvark_dns, install_conmon, install_mandown, install_netavark, install_passt, install_podman, install_runc, install_slirp4netns, setup_go

from ..dev.models import Debinfo, RepoName as er, Repo, Repos

from ..gpkgs.sudo import Sudo
from ..gpkgs import message as msg
from ..gpkgs import shell_helpers as shell
from ..gpkgs.semver import SemVer, semver

def get_repos(
    info:Debinfo,
    direpa_sources:str,
    podman_tag:str|None=None,
):
    drs:dict[er, Repo]=dict()
    for repo in info.repos:
        drs[repo.name]=repo
        set_repo(direpa_sources, repo, update=False)

    repos=Repos(**drs)
    if podman_tag is None:
        repos.podman.tag=get_latest_tag(repos.podman)
    else:    
        repos.podman.tag=podman_tag
    assert(repos.podman.tag is not None)
    info.version=repos.podman.tag
    if info.version[0] == "v":
        info.version=info.version[1:]

    commit_time=get_commit_time(repos.podman, repos.podman.tag)
    repos.podman.date=commit_time
    repos.runc.tag=get_closest_tag(repos.runc, commit_time, trigger_error=False)
    repos.conmon.tag=get_closest_tag(repos.conmon, commit_time, trigger_error=False)
    repos.passt.tag=get_closest_tag(repos.passt, commit_time, trigger_error=False)
    repos.netavark.tag=get_closest_tag(repos.netavark, commit_time, trigger_error=False)
    repos.aardvark_dns.tag=get_closest_tag(repos.aardvark_dns, commit_time, trigger_error=False)
    repos.go.tag=get_closest_tag(repos.go, commit_time, trigger_error=True)
    repos.image.tag=get_closest_tag(repos.image, commit_time, trigger_error=False)
    repos.slirp4netns.tag=get_closest_tag(repos.slirp4netns, commit_time, trigger_error=False)
    repos.rust.tag=get_closest_tag(repos.rust, commit_time, trigger_error=True)
    repos.mandown.tag=get_closest_tag(repos.mandown, commit_time, trigger_error=False)

    print_obj=dict()
    for key, value in drs.items():
        print_obj[key]=asdict(value)
    dump=json.dumps(print_obj, indent=4, sort_keys=True, default=str)
    return (repos, dump)

def clean(
    direpa_sources:str,
    direpa_assets:str,
    direpa_pkg:str,
    info:Debinfo,
    sudo:Sudo,
):
    sudo.enable()
    if os.path.exists(direpa_pkg):
        shell.cmd_prompt(["sudo", "rm", "-r", direpa_pkg])

    go_repo=[r for r in info.repos if r.name == er.GO][0]
    go_repo.path=os.path.join(direpa_sources, er.GO)
    go_repo.tag=get_latest_tag(go_repo)

    with setup_go(go_repo, direpa_assets):
        for repo in info.repos:
            direpa_repo=os.path.join(direpa_sources, repo.name)
            if os.path.exists(direpa_repo) is True:
                msg.info(f"At path '{direpa_repo}'")
                if os.path.exists(os.path.join(direpa_repo, "Makefile")):
                    os.chdir(direpa_repo)
                    stdout, stderr=subprocess.Popen(["make", "clean"]).communicate()

def update(
    direpa_sources:str,
    info:Debinfo,
):
    for repo in info.repos:
        set_repo(direpa_sources, repo, update=True)

def build_info(
    info:Debinfo,
    direpa_sources:str,
    podman_tag:str|None=None,
):
    os.makedirs(direpa_sources, exist_ok=True)
    repos, dump=get_repos(
        info=info,
        direpa_sources=direpa_sources,
        podman_tag=podman_tag,
    )

    print(dump)

def generate_md5sums(direpa_pkg):
    # md5sums
    # 99f31c0169430fae0c2a850a9ee9f1aa  usr/bin/podman
    filenpa_md5=os.path.join(direpa_pkg, "DEBIAN", "md5sums")
    direpa_usr=os.path.join(direpa_pkg, "usr")
    total_size = 0
    with open(filenpa_md5, "w") as f:
        for root, dirs, files in os.walk(direpa_usr):
            for elem in sorted(files):
                filenpa_usr=os.path.join(root, elem)
                if not os.path.islink(filenpa_usr):
                    total_size += os.stat(filenpa_usr).st_blocks * 512;
                short_path=os.path.relpath(filenpa_usr, direpa_pkg)
                with open(filenpa_usr, 'rb') as file_to_check:
                    data = file_to_check.read()
                    data_md5 = hashlib.md5(data).hexdigest()
                    f.write(f"{data_md5}  {short_path}\n")
    return int(total_size / 1024)


def build(
    info:Debinfo,
    direpa_sources:str,
    direpa_assets:str,
    direpa_pkg:str,
    direpa_builds:str,
    sudo:Sudo,
    podman_tag:str|None=None,
    # update:bool=True,
    # clean:bool=True,
):
    sudo.enable()
    if os.path.exists(direpa_pkg):
        shell.cmd_prompt(["sudo", "rm", "-r", direpa_pkg])

    subprocess.Popen(["mkdir", "-p", direpa_pkg]).communicate()
    filenpa_control=os.path.join(direpa_pkg, "DEBIAN", "control")
    cmd=["mkdir", "-p", os.path.dirname(filenpa_control)]
    subprocess.Popen(cmd).communicate()
  
    os.makedirs(direpa_sources, exist_ok=True)
    repos, dump=get_repos(
        info=info,
        direpa_sources=direpa_sources,
        podman_tag=podman_tag,
    )

    print(dump)

    add_conf(
        repo=repos.image,
        direpa_pkg=direpa_pkg,
        sudo=sudo,
        info=info,
    )


    if repos.mandown.tag is not None:
        filenpa_mandown=install_mandown(
            repo=repos.mandown,
            direpa_pkg=direpa_pkg,
        )
        assert(repos.rust.tag is not None)

        if repos.netavark.tag is not None:
            install_netavark(
                repo=repos.netavark,
                sudo=sudo,
                direpa_pkg=direpa_pkg,
                rust_tag=repos.rust.tag,
                filenpa_mandown=filenpa_mandown,
            )
        if repos.aardvark_dns.tag is not None:
            install_aardvark_dns(
                repo=repos.aardvark_dns,
                sudo=sudo,
                direpa_pkg=direpa_pkg,
                rust_tag=repos.rust.tag,
                filenpa_mandown=filenpa_mandown,
            )

    if repos.conmon.tag is not None:
        install_conmon(
            go_repo=repos.go,
            conmon_repo=repos.conmon,
            direpa_assets=direpa_assets,
            sudo=sudo,
            direpa_pkg=direpa_pkg,
        )
    if repos.passt.tag is not None:
        install_passt(
            repo=repos.passt,
            sudo=sudo,
            direpa_pkg=direpa_pkg,
        )
    if repos.runc.tag is not None:
        install_runc(
            go_repo=repos.go,
            runc_repo=repos.runc,
            direpa_assets=direpa_assets,
            sudo=sudo,
            direpa_pkg=direpa_pkg,
        )
    if repos.slirp4netns.tag is not None:
        install_slirp4netns(
            repo=repos.slirp4netns,
            direpa_assets=direpa_assets,
            sudo=sudo,
            direpa_pkg=direpa_pkg,
        )
    install_podman(
        go_repo=repos.go,
        podman_repo=repos.podman,
        direpa_assets=direpa_assets,
        sudo=sudo,
        direpa_pkg=direpa_pkg,
    )
    info.description=info.description.strip()
    info.description+="\n .\n Build dependencies:\n"
    dydata=json.loads(dump)
    for key, dy in sorted(dydata.items()):
        info.description+=f" * {dy['name']}: {dy['tag']} {dy['giturl']}\n"

    architecture=shell.cmd_get_value(["dpkg", "--print-architecture"])
    assert(architecture is not None)
    info.architecture=architecture
    installed_size=generate_md5sums(direpa_pkg)

    with open(filenpa_control, "w") as f:
        f.write(f"""Package: {info.package}
Architecture: {info.architecture}
Version: {info.version}
Section: {info.section}
Maintainer: {info.maintainer}
Priority: {info.priority}
Installed-Size: {installed_size}
Description: {info.description.strip()}
Depends: {", ".join(info.depends)}
Homepage: {info.homepage}
""")
        
    os.makedirs(direpa_builds, exist_ok=True)
    filenpa_deb=os.path.join(direpa_builds, f"podman2deb-{info.architecture}-{info.version}.deb")
    shell.cmd_prompt(["dpkg-deb", "-b", direpa_pkg, filenpa_deb])

def set_repo(
    direpa_sources:str,
    repo:Repo,
    update:bool,
):
    direpa_repo=os.path.join(direpa_sources, repo.name)
    repo.path=direpa_repo
    if os.path.exists(direpa_repo) is True:
        if update is True:
            msg.info(f"Repo '{repo.name}' at '{repo.giturl}'")
            os.chdir(direpa_repo)
            shell.cmd_prompt(["git", "fetch", "--tags"])
    else:
        msg.info(f"Repo '{repo.name}' at '{repo.giturl}'")
        if repo.name in [er.GO, er.RUST]:
            shell.cmd_prompt(["git", "clone", repo.giturl, direpa_repo])
        else:
            shell.cmd_prompt(["git", "clone", "--recurse-submodules", repo.giturl, direpa_repo])

def get_commit_time(repo:Repo, tag:str):
    assert(repo.path is not None)
    os.chdir(repo.path)
    output=shell.cmd_get_value([
        "git",
        "log",
        "-1",
        "--format=%aI",
        tag,
    ])
    assert(isinstance(output, str))
    # 2025-09-04T15:23:56-04:00
    return datetime.strptime(output, "%Y-%m-%dT%H:%M:%S%z")

def get_latest_tag(repo:Repo):
    assert(repo.path is not None)
    os.chdir(repo.path)
    output=shell.cmd_get_value([
        "git",
        "tag",
    ])
    assert(output is not None)
    tags=output.splitlines()
    versions=semver(tags, flatten=True, no_duplicates=True, skip_error=True, prefix=repo.prefix)
    versions.reverse()
    for v in versions:
        obj=SemVer(v, prefix=repo.prefix)
        if obj.pre == "":
            tag=v
            return tag
            
    raise Exception(f"No latest tag found at repo {repo.name}.")

def get_closest_tag(repo:Repo, commit_time:datetime, trigger_error:bool=False):
    assert(repo.path is not None)
    os.chdir(repo.path)
    output=shell.cmd_get_value([
        "git",
        "tag",
    ])
    assert(output is not None)
    tags=output.splitlines()
    versions:list[str]
    if repo.name == er.PASST:
        for t in sorted(tags, reverse=True):
            tmp_time=get_commit_time(repo, t)
            if tmp_time <= commit_time:
                repo.date=tmp_time
                return t
        if trigger_error is True:
            pprint(tags)
            raise Exception(f"No closest tag found at repo {repo.name} for time {commit_time}")
        else:
            return None
    elif repo.name == er.MANDOWN:
        tmp_tags=[]
        for t in tags:
            elems=t.split(".")
            if len(elems) > 3:
                elem=".".join(elems[:3])+"+"+elems[3]
                tmp_tags.append(elem)
            else:
                tmp_tags.append(t)

        versions=semver(tmp_tags, flatten=True, no_duplicates=True, skip_error=True, prefix=repo.prefix)
        versions=[v.replace("+", ".") for v in versions]

    else:
        versions=semver(tags, flatten=True, no_duplicates=True, skip_error=True, prefix=repo.prefix)
        versions.reverse()

    for v in versions:
        if "+" not in v:
            tag=v
            tmp_time=get_commit_time(repo, tag)
            if tmp_time <= commit_time:
                repo.date=tmp_time
                return tag

    if trigger_error is True:
        pprint(versions)
        raise Exception(f"No closest tag found at repo {repo.name} for time {commit_time}")
    else:
        return None

def list_tags(
    direpa_sources:str,
    repo:Repo,
    update:bool=False,
):
    set_repo(direpa_sources, repo, update)
    assert(repo.path is not None)
    os.chdir(repo.path)
    output=shell.cmd_get_value([
        "git",
        "tag",
    ])
    assert(output is not None)
    tags=output.splitlines()
    versions=sorted(semver(tags, flatten=True, no_duplicates=True, skip_error=True, prefix=repo.prefix))
    return versions
    