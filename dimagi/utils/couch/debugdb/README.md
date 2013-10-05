# Couchdbkit debug output for django-devserver

Install django-devserver

add `devserver` to your APPS or LOCAL_APPS

To your settings make sure `DEVSERVER_MODULES` has the devmodule added:

`DEVSERVER_MODULES = ('dimagi.utils.dev.couchdb_module.CouchDBDevModule',)`


If you want the full gory details of your couch use/abuse there are additional settings to add to your localsettings.py

`COUCHDB_DEVSERVER_VERBOSE=True # shows verbose output of views and gets`

`COUCHDB_DEVSERVER_STACKTRACE=True # shows last line of the stacktrace that calls the code in question`

`COUCHDB_DEVSERVER_STACK_SIZE=1 # integer number to specify lines of stack trace to show for view`

