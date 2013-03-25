LOG=pip.log
pip install --quiet --log="$LOG" --use-mirrors -r requirements/requirements.txt || cat $LOG
pip install --quiet --log="$LOG" --use-mirrors -r requirements/dev-requirements.txt || cat $LOG
