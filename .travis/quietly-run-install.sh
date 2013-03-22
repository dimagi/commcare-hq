LOG=install.log

(bash -ex install.sh > $LOG 2>&1 || cat $LOG) &

set +x
until [ -z "$(ps aux | egrep '[^-]install.sh')" ]; do echo -n '.'; sleep 1; done
set -x
