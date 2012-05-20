def get_server_url(server_root, username, password):
    if username and password:
        return "http://%(user)s:%(pass)s@%(server)s" % \
            {"user": username,
             "pass": password, 
             "server": server_root }
    else:
        return "http://%(server)s" % {"server": server_root }

def get_dynamic_db_settings(server_root, username, password, dbname, installed_apps):
    """
    Get dynamic database settings.  Other apps can use this if they want to change
    settings
    """
    
    server = get_server_url(server_root, username, password)
    database = "%(server)s/%(database)s" % {"server": server, "database": dbname}
    posturl = "http://%s/%s/_design/couchforms/_update/xform/" % (server_root, dbname)
    return {"COUCH_SERVER":  server,
            "COUCH_DATABASE": database,
            "XFORMS_POST_URL": posturl }
            

def get_commit_id():
    # This command is never allowed to fail since it's called in settings
    try:
        import os
        return os.popen("git log --format=%H -1").readlines()[0].strip()
    except Exception:
        return None

def make_couchdb_tuple(app_label, couch_database_url):
    """
    Helper function to generate couchdb tuples for mapping app name to couch database URL.

    In this case, the helper will magically alter the URL for special core libraries.

    Namely, auditcare, and couchlog
    """

    if app_label == 'auditcare' or app_label == 'couchlog':
        return app_label, "%s__%s" % (couch_database_url, app_label)
    else:
        return app_label, couch_database_url

