#!/bin/bash
# run as
# scripts/last_deploy.sh
# or as
# scripts/last_deploy.sh icds pna

if [ $# != 0 ]; then
    ENVS=$@
else
    ENVS=(icds-staging staging production india swiss icds pna)
fi

for i in ${ENVS[@]}; do
    git tag | grep deploy | grep "[0-9]\-${i}-deploy" | grep -v hot_fix | tail -n 1
done
