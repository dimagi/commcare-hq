from django.db.models import signals
from couchdbkit.loaders import FileSystemDocsLoader
import os
from dimagi.utils.couch.database import get_db
from couchdbkit import push

def sync_design_docs(app, **kwargs):
    """Function used by syncdb signal"""
    app_name = app.__name__.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    if app_label == "couchapps":
        dir = os.path.abspath(os.path.dirname(__file__))
        for d in [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]:
            push(os.path.join(dir, d), get_db(), force=True,
                 docid="_design/%s" % d)
            print "synced couchapp %s in couchdb" % d

signals.post_syncdb.connect(sync_design_docs)