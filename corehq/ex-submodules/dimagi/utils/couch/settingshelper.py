
from __future__ import absolute_import
from __future__ import unicode_literals


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
    return {
        "COUCH_SERVER":  server,
        "COUCH_DATABASE": database,
    }


def get_commit_id():
    # This command is never allowed to fail since it's called in settings
    try:
        import os
        return os.popen("git log --format=%H -1").readlines()[0].strip()
    except Exception:
        return None
