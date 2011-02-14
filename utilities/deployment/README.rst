CommCareHQ Deployment Utilities Scripts
=======================================

Upstart Scripts

couchdb - the couchdb upstart script
cchq_www - the main django server script
cchq_celeryd - the celery daemon for cchq


Symlink these to /etc/init/ in your ubuntu environment
run: initctl reload-configuration

start couchdb
(couchdb should fire up cchq_www, and cchq_ww should fire up cchq_celeryd)
to manage the services, do:
start/stop cchq_www or whatever.
