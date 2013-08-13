# Couchdbkit debug output for django-devserver

Install django-devserver

add `devserver` to your APPS or LOCAL_APPS

In DEVSERVER_MODULES = (), add `'dimagi.utils.dev.couchdb_module.CouchDBDevModule'` to it.

If you want the full gory details of your couch use/abuse, add a `COUCHDB_DEVSERVER_VERBOSE=True` variable to your settings as well.
If you want the stacktrace of your offending couch use/abuse, add a `COUCHDB_DEVSERVER_STACKTRACE=True` variable to your settings as well.
