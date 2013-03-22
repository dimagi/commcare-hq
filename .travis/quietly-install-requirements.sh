LOG=pip.log

(pip install -r requirements/requirements.txt > $LOG 2>&1 || cat $LOG) &
(pip install -r requirements/dev-requirements.txt > $LOG 2>&1 || cat $LOG) &

set +x
until [ -z "$(ps aux | grep 'pip install')" ]; do echo -n '.'; sleep 1; done
set -x
