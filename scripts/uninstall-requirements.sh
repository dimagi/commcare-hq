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
