#!/bin/bash
set -ev

# hard coded: "If jsonobject-couchdbkit==0.7.2.0 is installed, uninstall jsonobject"
# this is necessary to upgrade from 0.7.2.0 to 0.7.3.0
# because of a bug in how we were packaging jsonobject-couchdbkit earlier
# (the `jsonobject/` directory was being packaged in with jsonobject-couchdbkit inappropriately)
# feel free to delete this workaround after May 2016 (to be conservative)
pip freeze | grep jsonobject-couchdbkit==0.7.2.0 && pip uninstall jsonobject --yes

uninstall=requirements/uninstall-requirements.txt
tmp=requirements/uninstall-tmp.txt

join <(sort -n $uninstall) <(pip freeze | grep -v '^-' | cut -d'=' -f1 | sort -n) > $tmp
join <(sort -n $uninstall) <(pip freeze | grep -v '^-' | sort -n) >> $tmp

# if $tmp isn't just a single newline character
if [ -s $tmp ]
then
    pip uninstall -r $tmp --yes
fi
rm $tmp
