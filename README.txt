Put XForms in couchdb!

To include this in a django project you need the following settings defined in your settings.py


    ####### Couch Forms & Couch DB Kit Settings #######

    COUCH_SERVER_ROOT = 'localhost:5984'
    COUCH_USERNAME = ''
    COUCH_PASSWORD = ''
    COUCH_DATABASE_NAME = 'database_name'

    # you may want to import localsettings here so the variables above can be overridden

    def get_server_url(server_root, username, password):
        if username and password:
            return "http://%(user)s:%(pass)s@%(server)s" % \
                {"user": username,
                 "pass": password,
                 "server": server_root }
        else:
            return "http://%(server)s" % {"server": server_root }
    COUCH_SERVER = get_server_url(COUCH_SERVER_ROOT, COUCH_USERNAME, COUCH_PASSWORD)
    COUCH_DATABASE = "%(server)s/%(database)s" % {"server": COUCH_SERVER, "database": COUCH_DATABASE_NAME }


    XFORMS_POST_URL = "http://%s/%s/_design/couchforms/_update/xform/" % (COUCH_SERVER_ROOT, COUCH_DATABASE_NAME)
    COUCHDB_DATABASES = [(app_label, COUCH_DATABASE) for app_label in [
            'couchforms',
        ]
    ]


