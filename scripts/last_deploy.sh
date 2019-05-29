#!/bin/bash
# run as
# scripts/last_deploy.sh
# or as
# scripts/last_deploy.sh icds pna

if [ $# != 0 ]; then
    ENVS=$@
else
    ENVS=(staging production india swiss icds pna)
fi

for i in ${ENVS[@]}; do
    git tag | grep deploy | grep ${i} | grep -v hot_fix | tail -n 1
done
