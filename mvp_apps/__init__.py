from django.db.models import signals
from couchdbkit.loaders import FileSystemDocsLoader
import os
from dimagi.utils.couch.database import get_db
from couchdbkit import push
from couchdbkit.exceptions import ResourceNotFound

def get_couchapps():
    dir = os.path.abspath(os.path.dirname(__file__))
    return [d for d in os.listdir(dir) if os.path.isdir(os.path.join(dir, d))]

def sync_design_docs(db, temp=None):
    dir = os.path.abspath(os.path.dirname(__file__))
    for d in get_couchapps():
        design_name = '%s-%s' % (d, temp) if temp else d
        docid = "_design/%s" % design_name
        push(os.path.join(dir, d), db, force=True,
            docid=docid)
        print "synced mvp_app %s in couchdb" % d
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
    if app_label == "mvp_apps":
        sync_design_docs(get_db())

def copy_designs(db=None, temp='tmp', delete=True):
    db = db or get_db()
    for app_label in get_couchapps():
        print "Copy prepared design docs for `%s`" % app_label
        tmp_name = '%s-%s' % (app_label, temp)
        from_id = '_design/%s' % tmp_name
        to_id   = '_design/%s' % app_label
        try:
            db.copy_doc(from_id, to_id)
            if delete:
                del db[from_id]

        except ResourceNotFound:
            print '%s not found.' % (from_id, )



signals.post_syncdb.connect(catch_signal)