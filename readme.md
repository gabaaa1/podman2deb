# Podman2deb

This software builds podman from sources for Debian operating system. It allows to install the latest Podman version on Debian Bookworm for instance. Podman2deb automatically clone and build the following repositories: 
- aardvark-dns
- conmon
- go
- image
- netavark
- podman
- passt
- runc
- slirp4netns

Podman2deb creates then a deb package that allows to install Podman and all its more recent dependencies on a Debian operating system.

If these packages have been already installed through the package tool apt you may want to remove them first i.e.:
```shell
sudo apt-get remove aardvark-dns
sudo apt-get remove conmon
sudo apt-get remove netavark
sudo apt-get remove podman
sudo apt-get remove passt
sudo apt-get remove runc
sudo apt-get remove slirp4netns
```

## Commands:

```shell
# to prevent typing sudo password you can cache it temporarily with command. debkey is then use to execute sudo command with sudo python module in gpkgs dependencies.
export debkey=""
read -s debkey

# Clone or fetch tags for all repositories
main.py --update
# Clean previous builds for all repositories
main.py --clean
# Build all repositories for latest stable version of Podman
main.py --build
# Build all repositories with selected version of Podman
main.py --build --tag v5.6.1
# Provide build information for latest stable version of Podman
main.py --build-info
# Provide build information for selected version of Podman
main.py --build-info --tag v5.6.1
# List all available tags for Podman
main.py --list-tags
```

Podman2deb sources and gpkgs dependencies are available in the release section.

Build command will select for each repository the stable version that is closest in time to the selected Podman version.
Podman2deb may compile on different architectures as long as it is a Debian operating system.

The latest Podman version at the time v5.6.1 successfully compiles.

Then to install podman do:
```shell
sudo dpkg -i builds/Podman2deb-amd64-5.6.1.deb
# if error 
# Errors were encountered while processing: dependency problems - leaving unconfigured
# then run the command below to install missing dependencies
sudo apt --fix-broken install
```

Podman v5.6.1 seems to work fine on Debian Bookworm. I couldn't manage to compile older Podman versions, the build breaks at netavark package each time.

`Podman2deb-amd64-5.6.1.deb` is available in the releases section. 
