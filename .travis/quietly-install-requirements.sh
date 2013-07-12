LOG=pip.log

# --quiet is a bit too quiet because everything times out on travis

cat requirements/requirements.txt requirements/dev-requirements.txt | cut -d '#' -f 1 | egrep -v '^$' | \
while read line; do 
    if [ ! -z "$line" ]; then
        date
        echo pip install --use-mirrors "$line" 
        pip install --use-mirrors --use-wheel --find-links=/home/$USER/wheelhouse "$line" > "$LOG" 2>&1 || cat "$LOG"
    fi
done
date
