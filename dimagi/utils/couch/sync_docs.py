import os
from couchdbkit import push, RequestFailed
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.loading import couchdbkit_handler
import sys
from django.conf import settings


def sync_design_docs(db, design_dir, design_name, temp=None):
    """
    pushes design documents and brings new index up to date if temp

    for example it can be used to push new changes to the myapp design doc to
    _design/myapp-tmp

    and then trigger an index of _design/myapp-tmp

    """
    design_name_ = '%s-%s' % (design_name, temp) if temp else design_name
    docid = "_design/%s" % design_name_
    push(design_dir, db, force=True, docid=docid)
    print "synced '%s' in couchdb" % design_name
    if temp:
        # found in the innards of couchdbkit
        view_names = db[docid].get('views', {}).keys()
        if len(view_names) > 0:
            print 'Triggering view rebuild'
            view = '%s/%s' % (design_name_, view_names[0])
            while True:
                try:
                    list(db.view(view, limit=0))
                except RequestFailed as e:
                    if 'timeout' not in e.message:
                        raise
                else:
                    break


def copy_designs(db, design_name, temp='tmp', delete=True):
    print "Copy prepared design docs for '%s' in couchdb" % design_name
    tmp_name = '%s-%s' % (design_name, temp)
    from_id = '_design/%s' % tmp_name
    to_id = '_design/%s' % design_name
    try:
        db.copy_doc(from_id, to_id)
        if delete:
            del db[from_id]

    except ResourceNotFound:
        print '%s not found.' % (from_id, )


def sync(app, verbosity=2, temp=None):
    """
    All of this is copied from couchdbkit.ext.django.loading

    but the actual syncing code is replaced with our improved version

    """
    app_name = app.__name__.rsplit('.', 1)[0]
    app_labels = set()
    schema_list = couchdbkit_handler.app_schema.values()
    for schema_dict in schema_list:
        for schema in schema_dict.values():
            app_module = schema.__module__.rsplit(".", 1)[0]
            if app_module == app_name and not schema._meta.app_label in app_labels:
                app_labels.add(schema._meta.app_label)
    for app_label in app_labels:
        if not app_label in couchdbkit_handler._databases:
            continue
        if verbosity >=1:
            print "sync `%s` in CouchDB" % app_name
        db = couchdbkit_handler.get_db(app_label)

        app_path = os.path.abspath(os.path.join(sys.modules[app.__name__].__file__, ".."))
        design_path = "%s/%s" % (app_path, "_design")
        if not os.path.isdir(design_path):
            if settings.DEBUG:
                print >>sys.stderr, "%s don't exists, no ddoc synchronized" % design_path
            return

        # these lines differ from the original
        # and simply pass on the responsibility of syncing to our
        # improved method
        sync_design_docs(
            db=db,
            design_dir=os.path.join(app_path, "_design"),
            design_name=app_label,
            temp=temp,
        )
