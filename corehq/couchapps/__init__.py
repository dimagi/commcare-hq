from django.db.models import signals
from couchdbkit.loaders import FileSystemDocsLoader
import os
from dimagi.utils.couch.database import get_db
from couchdbkit import push

def sync_design_docs(db, temp=None):
    dir = os.path.abspath(os.path.dirname(__file__))
    for d in [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]:
        design_name = '%s-%s' % (d, temp) if temp else d
        docid = "_design/%s" % design_name
        push(os.path.join(dir, d), db, force=True,
             docid=docid)
        print "synced couchapp %s in couchdb" % d
        if temp:
            # found in the innards of couchdbkit
            view_names = db[docid].get('views', {}).keys()
            if len(view_names) > 0:
                print 'Triggering view rebuild'
                view = '%s/%s' % (design_name, view_names[0])
                list(db.view(view, limit=0))

    
def catch_signal(app, **kwargs):
    """Function used by syncdb signal"""
    app_name = app.__name__.rsplit('.', 1)[0]
    app_label = app_name.split('.')[-1]
    if app_label == "couchapps":
        sync_design_docs(get_db())

signals.post_syncdb.connect(catch_signal)