LOG=pip.log

echo Installing requirements/requirements.txt
pip install -r ../requirements/requirements.txt > $LOG 2>&1 || cat $LOG

echo Installing requirements/dev-requirements.txt
pip install -r ../requirements/dev-requirements.txt > $LOG 2>&1 || cat $LOG
