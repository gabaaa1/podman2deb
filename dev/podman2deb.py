#!/usr/bin/env python3
from pprint import pprint
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


from .install_deps import add_conf, install_aardvark_dns, install_conmon, install_netavark, install_passt, install_podman, install_runc, install_slirp4netns, setup_go

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
    repos.runc.tag=get_closest_tag(repos.runc, commit_time)
    repos.conmon.tag=get_closest_tag(repos.conmon, commit_time)
    repos.passt.tag=get_closest_tag(repos.passt, commit_time)
    repos.netavark.tag=get_closest_tag(repos.netavark, commit_time)
    repos.aardvark_dns.tag=get_closest_tag(repos.aardvark_dns, commit_time)
    repos.go.tag=get_closest_tag(repos.go, commit_time)
    repos.image.tag=get_closest_tag(repos.image, commit_time)
    repos.slirp4netns.tag=get_closest_tag(repos.slirp4netns, commit_time)

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
):
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
    install_netavark(
        repo=repos.netavark,
        sudo=sudo,
        direpa_pkg=direpa_pkg,
    )
    install_aardvark_dns(
        repo=repos.aardvark_dns,
        sudo=sudo,
        direpa_pkg=direpa_pkg,
    )
    install_conmon(
        go_repo=repos.go,
        conmon_repo=repos.conmon,
        direpa_assets=direpa_assets,
        sudo=sudo,
        direpa_pkg=direpa_pkg,
    )
    install_passt(
        repo=repos.passt,
        sudo=sudo,
        direpa_pkg=direpa_pkg,
    )
    install_runc(
        go_repo=repos.go,
        runc_repo=repos.runc,
        direpa_assets=direpa_assets,
        sudo=sudo,
        direpa_pkg=direpa_pkg,
    )
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

    with open(filenpa_control, "w") as f:
        f.write(f"""Package: {info.package}
Architecture: {info.architecture}
Version: {info.version}
Section: {info.section}
Maintainer: {info.maintainer}
Priority: {info.priority}
Description: {info.description.strip()}
Depends: {", ".join(info.depends)}
Homepage: {info.homepage}
""")
        
    os.makedirs(direpa_builds, exist_ok=True)
    filenpa_deb=os.path.join(direpa_builds, f"debpodman-{info.architecture}-{info.version}.deb")
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
        shell.cmd_prompt(["git", "clone", repo.giturl, direpa_repo])

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

def get_closest_tag(repo:Repo, commit_time:datetime):
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
        pprint(tags)
        raise Exception(f"No closest tag found at repo {repo.name} for time {commit_time}")

    else:
        versions=semver(tags, flatten=True, no_duplicates=True, skip_error=True, prefix=repo.prefix)
        versions.reverse()


    for v in versions:
        obj=SemVer(v, prefix=repo.prefix)
        if obj.pre == "":
            tag=v
            tmp_time=get_commit_time(repo, tag)
            repo.date=tmp_time
            if tmp_time <= commit_time:
                return tag
    pprint(versions)
    raise Exception(f"No closest tag found at repo {repo.name} for time {commit_time}")

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
    