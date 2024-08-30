#!/usr/bin/env bash

if [ -z "$SUDO_USER" ]; then
    echo "This script is intended to be run as sudo. Exiting"
    exit 1
fi

UBUNTU_MAJOR_VERS=$(lsb_release -rs | cut -c-2)

add_sources () {
    if [[ "$UBUNTU_MAJOR_VERS" -ge "23" ]]; then
        # appropriate podman versions are already available
        return
    fi

    if [ ! -f /etc/apt/sources.list.d/devel:kubic:libcontainers:unstable.list ]; then
        mkdir -p /etc/apt/keyrings
        curl -fsSL "https://download.opensuse.org/repositories/devel:kubic:libcontainers:unstable/xUbuntu_$(lsb_release -rs)/Release.key" \
          | gpg --dearmor \
          | tee /etc/apt/keyrings/devel_kubic_libcontainers_unstable.gpg > /dev/null
        # NOTE: opensuse seems to be having https difficulties, so switching to http temporarily
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/devel_kubic_libcontainers_unstable.gpg]\
            http://download.opensuse.org/repositories/devel:kubic:libcontainers:unstable/xUbuntu_$(lsb_release -rs)/ /" \
          | tee /etc/apt/sources.list.d/devel:kubic:libcontainers:unstable.list > /dev/null
        apt-get update -qq
    fi
}

#add_sources

# Clean previous podman installations, just in case
apt remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

#rm -f /etc/systemd/system/docker.socket
#rm -f /etc/systemd/system/sockets.target.wants/docker.socket
#rm -f /etc/systemd/system/multi-user.target.wants/docker.service

# Also might want to take care of /var/lib/docker (containers and images still stored here)

#rm -f /etc/systemd/system/podman.service
#rm -f /etc/systemd/system/podman-restart.service
#rm -f /etc/systemd/system/podman-auto-update.service
#rm -f /etc/systemd/system/podman-auto-update.timer

#rm -f /etc/systemd/user/podman.service
#rm -f /etc/systemd/user/default.target.wants/podman.service
#rm -f /etc/systemd/user/sockets.target.wants/podman.socket
#rm -f /etc/xdg/systemd/user/podman.socket
#systemctl  --user daemon-reload

#Also look in /usr/lib/systemd/user/podman.socket
# /usr/lib/systemd/user/podman.service

apt install -y podman podman-docker
apt install -y systemd-container  # Necessary to load the socket within this script

if [[ "$UBUNTU_MAJOR_VERS" -lt "23" ]]; then
    # not ignoring recommended packages pulls a normal docker install -- we just need the docker-compose binary
    #apt install --no-install-recommends -y docker-compose

    # Fix a bug that ships with 22.04
    curl -O --output-dir "/tmp" http://archive.ubuntu.com/ubuntu/pool/universe/g/golang-github-containernetworking-plugins/containernetworking-plugins_1.1.1+ds1-3_amd64.deb
    apt install /tmp/containernetworking-plugins_1.1.1+ds1-3_amd64.deb
    rm /tmp/containernetworking-plugins_1.1.1+ds1-3_amd64.deb
fi

# Install flatpak
apt install -y flatpak
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub io.podman_desktop.PodmanDesktop

# Mimic docker-compose support
USER_HOME=$(eval echo ~$SUDO_USER)
DOCKER_BIN_FOLDER=${USER_HOME}/.local/bin
DOCKER_DEST=${DOCKER_BIN_FOLDER}/docker

mkdir -p $DOCKER_BIN_FOLDER
cp setup/fake-docker $DOCKER_DEST
chown -R $SUDO_UID:$SUDO_GID $DOCKER_DEST

echo "export DOCKER_HOST=unix://\$XDG_RUNTIME_DIR/podman/podman.sock" >> $USER_HOME/.bashrc
echo "export DOCKER_SOCK=\$XDG_RUNTIME_DIR/podman/podman.sock" >> $USER_HOME/.bashrc

echo "PATH=\$HOME/.local/bin:\$PATH" >> $USER_HOME/.bashrc

#sudo -u $SUDO_USER systemctl --user enable --now podman.socket
machinectl shell $SUDO_USER@ $(which systemctl) --user enable --now podman.socket
