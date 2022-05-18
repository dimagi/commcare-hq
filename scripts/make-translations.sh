function abort () {
    echo $@
    echo "Aborting."
    exit 1
}

echo "Gathering all translation strings.  Note that this will probably take a while"
./manage.py makemessages --all --ignore 'corehq/apps/app_manager/tests/data/v2_diffs*' --ignore 'node_modules' --ignore 'docs/_build' "$@"

echo "Gathering javascript translation strings.  This will also probably take a while"
./manage.py makemessages -d djangojs --all --ignore 'corehq/apps/app_manager/tests/data/v2_diffs*' --ignore 'node_modules' --ignore 'docs' "$@"

echo "Compiling translation files."
if ! ./manage.py compilemessages; then
    echo ""
    echo "'./manage.py compilemessages' failed.  This is probably due to a bad translation, maybe a translator messed up a format string or something."
    echo "If the deploy is urgent, it might be best to drop the changes to locale/ and deploy without updating translations, then assign an interrupt ticket to fix."
    echo "The output above from compilemessages should have specifics about the locale/ file and line where the error(s) occurred."
    echo "1. Open those files, go to the appropriate lines and fix the errors."
    echo "2. Run './manage.py compilemessages' again to make sure it's fixed."
    echo "3. Run 'tx push -s -t' to update them on transifex."
    echo "4. Now if you do 'git checkout -- locale' and run this script again, it should succeed."
    echo "5. You should probably also reach out to the translator to make sure they don't mess this up again."
    abort
fi

# Remove diffs for files where the only thing that changed was POT-Creation-Date
# Todo: It's a bit hacky that this relies on git state to undo unncessary changes
# Todo: Ideally we'd change the management commands above to just not produce the diff in the first place
git diff --name-only | grep '^locale/' | while read -r filename
do
    if ! git diff -U0 -- "$filename" | tail -n +6 | grep -v '^[+-]"POT-Creation-Date:\s' > /dev/null
    then
        git checkout -- "$filename"
    fi
done
