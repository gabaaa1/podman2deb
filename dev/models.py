#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from dataclasses import dataclass
from enum import StrEnum, auto

class RepoName(StrEnum):
    PODMAN=auto()
    RUNC=auto()
    CONMON=auto()
    PASST=auto()
    NETAVARK=auto()
    AARDVARK_DNS=auto()
    GO=auto()
    IMAGE=auto()
    SLIRP4NETNS=auto()
    RUST=auto()
    MANDOWN=auto()

@dataclass
class Repos:
    podman:"Repo"
    runc:"Repo"
    conmon:"Repo"
    passt:"Repo"
    netavark:"Repo"
    aardvark_dns:"Repo"
    go:"Repo"
    image:"Repo"
    slirp4netns:"Repo"
    rust:"Repo"
    mandown:"Repo"

@dataclass
class Debinfo:
    depends: list[str]
    package: str
    architecture: str
    version: str
    section: str
    maintainer: str
    priority: str
    homepage: str
    description: str
    repos: list["Repo"]
    registries: list[str]

@dataclass
class Repo:
    name: "RepoName"
    giturl: str
    path: str|None=None
    tag: str|None=None
    date: datetime|None=None
    download: str|None=None
    prefix: str=""

