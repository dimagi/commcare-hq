in commcare-hq root, run

bash app_builder_live_test/fetch_app_source.sh $username app_builder_live_test/hitlist.txt

Checkout master and then run

./manage.py build_apps app_builder_live_test/ master

Checkout feature branch and run

./manage.py build_apps app_builder_live_test/ feature

Then do a diff on the two directories:

diff -r app_builder_live_test/master app_builder_live_test/feature

OR

Just run ./app_builder_live_test/diff feature
