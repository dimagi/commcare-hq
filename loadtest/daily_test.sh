#!/bin/bash

DIR=`dirname $0`
CODE_ROOT=`dirname $DIR`

VENV_FILE=$CODE_ROOT/../python_env/bin/activate
if [ -f $VENV_FILE ]; then
    source $VENV_FILE
elif [ $VIRTUAL_ENV ]; then
    source $VIRTUAL_ENV/bin/activate
else
    echo "Couldn't find virtual env"
    exit 1
fi

# I would love to get rid of this:
sudo apt-get build-dep python-matplotlib
pip install -r $CODE_ROOT/requirements/loadtest-requirements.txt

cp $DIR/config.cfg.example $DIR/config.cfg
cd $CODE_ROOT
python -c '
import settings
db_settings = settings.DATABASES["default"]
db_settings["PORT"] = db_settings.get("PORT", "") or "5432"
print "results_database = postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(
    **db_settings
)
' >> $DIR/config.cfg

multimech-run `basename $DIR`
