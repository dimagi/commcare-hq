Developer FAQ
-------------

This is a starting point for troubleshooting issues that frequently occur once your local environment
is set up and you've started working on a singnificant code change.

TODO: make these links and/or answers
+ I created local forms and/or cases, but I don't see them in reports.
+ I created local cases, but some other part of HQ that filters by case type doesn't show my case types.
+ My local downloads/uploads aren't working
+ My JS/LESS changes aren't showing up (caching, staticfiles)
+ Web Apps and/or App Preview aren't working at all
+ My local app doesn't appear in Web Apps
+ My web server is throwing a slew of web socket errors

+ General advice: TODO: give yourself a test subscription, use commcare-devs for advice
+ Running Tests TODO pull from DEV_SETUP
+ Generating test data
+ Keeping ElasticSearch up to date TODO pull from document
+ Troubleshooting Formplayer TODO pull from document




TODO: move this back into DEV_SETUP
+ If you have an authentication error running `./manage.py migrate` the first
  time, open `pg_hba.conf` (`/etc/postgresql/9.1/main/pg_hba.conf` on Ubuntu)
  and change the line "local all all peer" to "local all all md5".

+ When running `./manage.py sync_couch_views`:
   + First time running `sync_couch_views`
      + 401 error related to nonexistent database:
         $ curl -X PUT http://localhost:5984/commcarehq  # create the database
         $ curl -X PUT http://localhost:5984/_config/admins/commcarehq -d '"commcarehq"' . # add admin user
      + Error stemming from any Python modules: the issue may be that your virtualenv is relying on the `site-packages` directory of your local Python installation for some of its requirements. (Creating your virtualenv with the `--no-site-packages` flag should prevent this, but it seems that it does not always work). You can check if this is the case by running `pip show {name-of-module-that-is-erroring}`. This will show the location that your virtualenv is pulling that module from; if the location is somewhere other than the path to your virtualenv, then something is wrong. The easiest solution to this is to remove any conflicting modules from the location that your virtualenv is pulling them from (as long as you use virtualenvs for all of your Python projects, this won't cause you any issues).
    + If you encounter an error stemming from an Incompatible Library Version of libxml2.2.dylib on Mac OS X, try running the following commands:

            $ brew install libxml2
	        $ brew install libxslt
	        $ brew link libxml2 --force
	        $ brew link libxslt --force

	+ If you encounter an authorization error related to CouchDB, try going to your `localsettings.py` file and change `COUCH_PASSWORD` to an empty string.
