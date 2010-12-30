This is a debug toolbar panel for adding couch trace/performance logging


Setting up:

In your settings.py, INSTALLED_APPS, add:
    'debug_toolbar', #duh, this needs to be enabled for it all to work.
    'dimagi.utils.couch.couchdebugpanel',

In your DEBUG_TOOLBAR_PANELS, add:
   'dimagi.utils.couch.couchdebugpanel.CouchDBLoggingPanel'
   #you should also consider disablign the LoggingPanel because couchdbkit/restkit uses extensive logging by default.  Either suppress the logging level on couchdbkit or just disable this panel.


In your settings_local, under LOCAL_APP_URLS, add this line:
    (r'', include('dimagi.utils.couch.couchdebugpanel.urls')),

    This is because the debug toolbar doesn't do a very good job scanning for other panel URLs.

Finally, this plugin has a bit of javascript to render itself prettily like the debug toolbar

