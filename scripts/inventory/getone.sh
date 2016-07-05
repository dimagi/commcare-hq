#!/usr/bin/env bash
# usage: scripts/inventory/getone.sh <environment> <group> [<n>]
#
#   environment   production, staging, or softlayer
#   group         webworkers, postgresql, proxy, etc.
#   n             the ordinal of the machine to pick if more than one
#
# Examples
#   scripts/inventory/getone.sh production postgresql
#   scripts/inventory/getone.sh production webworkers 2
#
# if <n> is greater than the total number, the last machine is picked

env=$1
group=$2
i=$3
TEMP=$(mktemp /tmp/sshinventory.XXX)
scripts/inventory/getinventory.py ${env} ${group} > ${TEMP}
COUNT=$(cat ${TEMP} | wc -l | sed 's/ *//g')
if [[ ${COUNT} != '1' && -z ${i} ]]
then
    echo "There are ${COUNT} ${env} ${group} machines:" >&2
    echo >&2
    cat ${TEMP} >&2
    echo >&2
    echo 'Use `'"$0 ${env} ${group} 1"'` to get the first' >&2
    exit -1
fi

if [[ -z ${i} ]]
then
    CHOICE=$(cat ${TEMP} | head -n1)
else
    CHOICE=$(cat ${TEMP} | head -n${i} | tail -n1)
fi

rm ${TEMP}
echo "${CHOICE}"
