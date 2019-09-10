#!/bin/bash
set -e
uninstall=$1
if [[ -z "${uninstall}" ]]
then
    uninstall=requirements/uninstall-requirements.txt
fi
tmp=requirements/uninstall-tmp.txt

join <(grep -v '#' ${uninstall} | sort -n) <(pip freeze | grep -v '^-' | cut -d'=' -f1 | sort -n) > ${tmp}
join <(grep -v '#' ${uninstall} | sort -n) <(pip freeze | grep -v '^-' | sort -n) >> ${tmp}

# if ${tmp} isn't just a single newline character
if [ -s ${tmp} ]
then
    echo "Uninstalling from ${uninstall}"
    pip uninstall -r ${tmp} --yes
else
    echo "Nothing to uninstall from ${uninstall}"
fi
rm ${tmp}
