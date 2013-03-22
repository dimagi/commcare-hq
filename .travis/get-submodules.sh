git submodule foreach --recursive 'git checkout master; git pull &'
until [ -z "$(ps aux | grep '[g]it pull')" ]; do sleep 1; done
