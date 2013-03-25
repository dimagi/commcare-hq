LOG=pip.log

# --quiet is a bit too quiet because everything times out on travis

cat requirements/requirements.txt requirements/dev-requirements.txt | \
while read line; do 
    if [ ! -z "$line" ]; then
        pip install --quiet --log="$LOG" --use-mirrors --quiet "$line" || cat $LOG
    fi
done
