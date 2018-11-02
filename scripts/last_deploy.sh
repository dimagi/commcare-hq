#!/bin/bash
# run as
# scripts/last_deploy.sh
# or as
# scripts/last_deploy.sh icds pna

if [ $# != 0 ]; then
    ENVS=$@
else
    ENVS=(staging production softlayer swiss icds pna)
fi

for i in ${ENVS[@]}; do
    git tag | grep deploy | grep ${i} | tail -n 1
done
