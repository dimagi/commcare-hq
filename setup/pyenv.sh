#!/usr/bin/env -S bash -i

# the above shebang causes the script to run in interactive mode.
# Without interactive mode, the default Ubuntu .bashrc exits immediately, so the below `source` command will fail
# There is probably a much better way to handle this

curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

echo 'export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"' >> $HOME/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> $HOME/.bashrc
# reboot shell to read the pyenv configuration
source $HOME/.bashrc

pyenv install 3.9.18
pyenv global 3.9.18
pyenv virtualenv 3.9.18 hq
pyenv local hq

# configure HQ
git submodule update --init --recursive
git-hooks/install.sh
pip install -r requirements/dev-requirements.txt
cp localsettings.example.py localsettings.py
mkdir sharedfiles
