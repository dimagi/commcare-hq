LOG=pip.log

# --quiet is a bit too quiet because everything times out on travis

cat requirements/requirements.txt requirements/dev-requirements.txt | \
while read line; do 
    if [ ! -z "$line" ]; then
        echo pip install --use-mirrors "$line" 
        pip install --use-mirrors "$line" > "$LOG" 2>&1 || cat "$LOG"
    fi
done
