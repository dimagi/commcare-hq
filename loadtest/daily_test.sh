#!/bin/bash

DIR=`dirname $0`

pip install -r requirements/loadtest-requirements.txt

cp $DIR/config.cfg.example $DIR/config.cfg
python -c '
import settings
print "results_database = postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}".format(
    **settings.DATABASES["default"]
)
' >> loadtest/config.cfg

multimech-run $DIR
