Common issues
-------------

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

+ On Windows, to get python-magic to work you will need to install the following dependencies.
  Once they are installed make sure the install folder is on the path.
  + [GNUWin32 regex][regex]
  + [GNUWin32 zlib][zlib]
  + [GNUWin32 file][file]

 [regex]: http://sourceforge.net/projects/gnuwin32/files/regex/
 [zlib]: http://sourceforge.net/projects/gnuwin32/files/zlib/
 [file]: http://sourceforge.net/projects/gnuwin32/files/file/

+ On Windows, if Celery gives this error on startup: `TypeError: 'LazySettings' object is not iterable` apply the
  changes decribed in this bug report comment: https://github.com/celery/django-celery/issues/228#issuecomment-13562642
