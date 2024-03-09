if [ -z "$SUDO_USER" ]; then
    echo "This script is intended to be run as sudo. Exiting"
    exit 1
fi

# TODO: detect and toggle between bash and zsh

add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.9 python3.9-dev python3-pip python3-venv

# Install pre-requisite libraries
apt install -y libncurses-dev libxml2-dev libxmlsec1-dev \
libxmlsec1-openssl libxslt1-dev libpq-dev pkg-config gettext make build-essential \
libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev

apt install -y curl
# XClip (optional for scripting)
apt install -y xclip

# Install JDK
apt install -y openjdk-17-jre

# Install Postgress Client (optional)
apt install -y postgresql-client

setup/node.sh
