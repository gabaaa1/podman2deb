#!/usr/bin/env python3
from contextlib import contextmanager
import os
from re import sub
import sys
import subprocess
import requests
import shutil
import tarfile
import tempfile

from .models import Debinfo, Repo

from ..gpkgs.sudo.dev.sudo import Sudo
from ..gpkgs import message as msg
from ..gpkgs import shell_helpers as shell

@contextmanager
def setup_go(
    repo:Repo,
    direpa_assets:str,
):
    filengo=f"{repo.tag}.linux-amd64.tar.gz"
    file_url=f"{repo.download}/{filengo}"
    filenpa_go=os.path.join(direpa_assets, filengo)
    if os.path.exists(filenpa_go) is False:
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            with open(filenpa_go, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"File '{filenpa_go}' downloaded successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error during download: {e}")

    direpa_go=os.path.join(direpa_assets, "go")
    if os.path.exists(direpa_go) is False:
        try:
            with tarfile.open(filenpa_go, 'r:gz') as tar_file:
                tar_file.extractall(path=direpa_assets)
            print(f"Successfully extracted '{filenpa_go}' to '{direpa_assets}'")
        except tarfile.ReadError:
            print(f"Error: Could not open or read '{filenpa_go}'. It might be corrupted or not a valid tar.gz file.")
        except FileNotFoundError:
            print(f"Error: Archive file not found at '{filenpa_go}'.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
    direpa_go_bin=os.path.join(direpa_go, "bin")
    allpaths=os.environ["PATH"].split(":")
    if direpa_go_bin not in allpaths:
        os.environ["PATH"]=f'{direpa_go_bin}:{os.environ["PATH"]}'


    tmppath=tempfile.TemporaryDirectory()
    filenpa_bin_go=os.path.join(direpa_go_bin, "go")
    try:
        os.environ["GOCACHE"]=tmppath.name
        os.environ["GO"]=filenpa_bin_go
        yield 
    finally:
        tmppath.cleanup()

def title(package:str):
    print()
    msg.info(f"############################")
    msg.info(f"# INSTALLING {package.upper()}")
    msg.info(f"############################")

def install_conmon(
    go_repo:Repo,
    conmon_repo:Repo,
    direpa_assets:str,
    sudo:Sudo,
    direpa_pkg:str,
    clean:bool=False,
):
    with setup_go(go_repo, direpa_assets):
        title(conmon_repo.name)
        os.environ["DESTDIR"]=direpa_pkg
        assert(conmon_repo.path is not None)
        msg.info(f"At path {conmon_repo.path}")
        os.chdir(conmon_repo.path)
        checkout(conmon_repo)
        if clean is True:
            shell.cmd_prompt(["make", "clean"])
        shell.cmd_prompt(["make"])
        if os.path.exists(os.path.join(conmon_repo.path, "tools")):
            stdout, stderr=subprocess.Popen(["make", "install.tools"], stderr=subprocess.PIPE).communicate()
            if stderr is not None:
                stderr=stderr.decode().strip()
                if len(stderr) > 0:
                    if "No rule to make target 'install.tools'" not in stderr:
                        if "Nothing to be done for 'all'" not in stderr:
                            raise Exception(stderr)
        sudo.enable()
        shell.cmd_prompt(["sudo", "-E", "make", "podman"])
        md2man=shutil.which("go-md2man")
        assert(md2man is not None)
        os.environ["GOMD2MAN"]=md2man
        shell.cmd_prompt(["sudo", "-E", "make", "install"])

def install_passt(
    repo:Repo,
    sudo:Sudo,
    direpa_pkg:str,
    clean:bool=False,
):
    title(repo.name)
    os.environ["DESTDIR"]=direpa_pkg
    assert(repo.path is not None)
    msg.info(f"At path {repo.path}")
    os.chdir(repo.path)
    checkout(repo)
    if clean is True:
        shell.cmd_prompt(["make", "clean"])
    shell.cmd_prompt(["make"])
    sudo.enable()
    shell.cmd_prompt(["sudo", "-E", "make", "install"])

def install_runc(
    go_repo:Repo,
    runc_repo:Repo,
    direpa_assets:str,
    sudo:Sudo,
    direpa_pkg:str,
    clean:bool=False,
):
    with setup_go(go_repo, direpa_assets):
        title(runc_repo.name)
        os.environ["DESTDIR"]=direpa_pkg
        assert(runc_repo.path is not None)
        msg.info(f"At path {runc_repo.path}")
        os.chdir(runc_repo.path)
        checkout(runc_repo)
        if clean is True:
            shell.cmd_prompt(["make", "clean"])
        shell.cmd_prompt(["make", "BUILDTAGS=selinux apparmor seccomp"])
        sudo.enable()
        shell.cmd_prompt(["sudo", "-E", "make", "install"])

def add_conf(
    repo: Repo,
    direpa_pkg:str,
    sudo:Sudo,
    info:Debinfo,
):
    direpa_containers=os.path.join(direpa_pkg, "etc", "containers")
    os.makedirs(direpa_containers, exist_ok=True)
    assert(repo.path is not None)
    msg.info(f"At path {repo.path}")
    os.chdir(repo.path)

    filenpa_conffiles=os.path.join(direpa_pkg, "DEBIAN", "conffiles")
    if os.path.exists(filenpa_conffiles) is False:
        open(filenpa_conffiles, "w").close()

    registryconf="registries.conf"
    policyconf="default-policy.json"
    for filen_conf in [
        registryconf,
        policyconf,
    ]:
        if os.path.exists(filen_conf):
            file_dst=os.path.join(direpa_containers, filen_conf)
            with open(filen_conf, "r") as f:
                with open(file_dst, "w") as g:
                    g.write(f.read())
                    if filen_conf == "registryconf":
                        text_registries='\", \"'.join(info.registries)
                        g.write(f'unqualified-search-registries=["{text_registries}"]')
            sudo.enable()
            shell.cmd_prompt(["sudo", "chown", "root:root", file_dst])

            with open(filenpa_conffiles, "a") as f:
                f.write(f"/etc/containers/{filen_conf}\n")

def set_rust(direpa_repo:str, rust_tag:str):
    if shutil.which("cargo") is None:
        raise Exception("""Rust needs to be installed on your system:
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
            . "$HOME/.cargo/env"
        """)
    
    os.chdir(direpa_repo)
    shell.cmd_prompt(["rustup", "override", "set", rust_tag])
    shell.cmd_prompt(["rustc", "--version"])

def install_mandown(
    repo:Repo,
    direpa_pkg:str,
    clean:bool=False,
):
    title(repo.name)
    os.environ["DESTDIR"]=direpa_pkg
    assert(repo.path is not None)
    msg.info(f"At path {repo.path}")
    os.chdir(repo.path)
    checkout(repo)
    if clean is True:
        subprocess.Popen(["make", "clean"]).communicate()
    shell.cmd_prompt(["make"])
    filenpa_mdn=os.path.join(repo.path, "mdn")
    shell.cmd_prompt(["chmod", "+x", filenpa_mdn])
    return filenpa_mdn

def install_netavark(
    repo:Repo,
    direpa_pkg:str,
    sudo:Sudo,
    rust_tag:str,
    filenpa_mandown:str,
    clean:bool=False,
):
    title(repo.name)
    assert(repo.path is not None)
    set_rust(repo.path, rust_tag)
    os.environ["DESTDIR"]=direpa_pkg
    os.environ["MANDOWN"]=filenpa_mandown
    msg.info(f"At path {repo.path}")
    os.chdir(repo.path)
    checkout(repo)
    if clean is True:
        shell.cmd_prompt(["make", "clean"])
    shell.cmd_prompt(["make"])
    shell.cmd_prompt(["make", "docs"])
    sudo.enable()
    shell.cmd_prompt(["sudo", "-E", "make", "install"])

def install_aardvark_dns(
    repo:Repo,
    direpa_pkg:str,
    sudo:Sudo,
    rust_tag:str,
    filenpa_mandown:str,
    clean:bool=False,
):
    title(repo.name)
    assert(repo.path is not None)
    set_rust(repo.path, rust_tag)
    os.environ["DESTDIR"]=direpa_pkg
    os.environ["MANDOWN"]=filenpa_mandown
    msg.info(f"At path {repo.path}")
    os.chdir(repo.path)
    checkout(repo)

    if clean is True:
        subprocess.Popen(["make", "clean"]).communicate()
    shell.cmd_prompt(["make"])
    sudo.enable()
    shell.cmd_prompt(["sudo", "-E", "make", "install"])

def install_slirp4netns(
    repo:Repo,
    direpa_pkg:str,
    direpa_assets:str,
    sudo:Sudo,
):
    title(repo.name)
    arch=shell.cmd_get_value(["uname", "-m"])
    filenbin=f"{repo.name}-{arch}"
    file_url=f"{repo.giturl}/releases/download/{repo.tag}/{filenbin}"
    filenpa_bin=os.path.join(direpa_assets, filenbin+f"-{repo.tag}")
    if os.path.exists(filenpa_bin) is False:
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            with open(filenpa_bin, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"File '{filenpa_bin}' downloaded successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error during download: {e}")

    direpa_dst=os.path.join(direpa_pkg, "usr", "bin")
    sudo.enable()
    shell.cmd_prompt(["sudo", "mkdir", "-p", direpa_dst])
    filenpa_dst=os.path.join(direpa_dst, repo.name)
    shell.cmd_prompt(["sudo", "cp", filenpa_bin, filenpa_dst])
    shell.cmd_prompt(["sudo", "chown", "root:root", filenpa_dst])
    shell.cmd_prompt(["sudo", "chmod", "+x", filenpa_dst])

def install_podman(
    go_repo:Repo,
    podman_repo:Repo,
    direpa_pkg:str,
    direpa_assets:str,
    sudo:Sudo,
    clean:bool=False,
):
    with setup_go(go_repo, direpa_assets):
        title(podman_repo.name)
        os.environ["DESTDIR"]=direpa_pkg
        assert(podman_repo.path is not None)
        msg.info(f"At path {podman_repo.path}")
        os.chdir(podman_repo.path)
        checkout(podman_repo)
        if clean is True:
            shell.cmd_prompt(["make", "clean"])
        shell.cmd_prompt(["make", "BUILDTAGS=exclude_graphdriver_devicemapper apparmor selinux seccomp systemd"])
        sudo.enable()
        shell.cmd_prompt(["sudo", "-E", "make", "install"])

def checkout(repo:Repo):
    stdout, stderr=subprocess.Popen(["git", "describe", "--exact-match", "--tags"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    current_tag:str|None=None
    if stdout is not None:
        current_tag=stdout.decode().strip()
    if current_tag != repo.tag:
        shell.cmd_prompt(["git", "clean", "-fd"])
        shell.cmd_prompt(["git", "checkout", repo.tag])