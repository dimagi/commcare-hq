from django.conf import settings
from couchdbkit.client import Server
import logging
import time

MAX_TRIES = 10

def delete(server, dbname):
    """
    Deletes a database, trying many times before failing.  This is because
    couch doesn't like deleting databases in windows.
    """
    tries = 0
    e = "UNKNOWN REASON"
    while tries < MAX_TRIES:
        try:                 
            server.delete_db(dbname)
            return
        except Exception, e: 
            # logging.error("Can't delete database %s.  %s" % (dbname, e))
            tries += 1
    if tries == MAX_TRIES:
        raise Exception("Unable to delete %s after %s tries.  Because: %s" % \
                        (dbname, MAX_TRIES, e))