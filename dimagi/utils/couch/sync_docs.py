import logging
import os
import sys
from collections import namedtuple

from couchdbkit import push, RequestFailed
from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.loading import couchdbkit_handler
from django.conf import settings

log = logging.getLogger(__name__)


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
    log.info("synced '%s' in couchdb", design_name)
    if temp:
        # found in the innards of couchdbkit
        view_names = db[docid].get('views', {}).keys()
        if len(view_names) > 0:
            log.info('Triggering view rebuild')
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
    log.info("Copy prepared design docs for '%s' in couchdb", design_name)
    tmp_name = '%s-%s' % (design_name, temp)
    from_id = '_design/%s' % tmp_name
    to_id = '_design/%s' % design_name
    try:
        db.copy_doc(from_id, to_id)
        if delete:
            del db[from_id]

    except ResourceNotFound:
        log.warning('%s not found.', from_id)


def sync(app, verbosity=2, temp=None):
    """
    This is copied and modified from couchdbkit.ext.django.loading.

    The actual syncing code is replaced with our improved version
    """
    app_sync_info = get_app_sync_info(app)

    for design_info in app_sync_info.designs:
        if verbosity >=1:
            log.info("sync `%s` in CouchDB", app_sync_info.name)

        if design_info.design_path is None and settings.DEBUG:
            log.warning("%s doesn't exist, no ddoc synchronized", design_info.design_path)
            continue

        # these lines differ from the original
        # and simply pass on the responsibility of syncing to our
        # improved method
        sync_design_docs(
            db=design_info.db,
            design_dir=design_info.design_path,
            design_name=design_info.app_label,
            temp=temp,
        )


AppSyncInfo = namedtuple('AppSyncInfo', ['name', 'designs'])
DesignInfo = namedtuple('DesignInfo', ['db', 'app_label', 'design_path'])


def get_app_sync_info(app):
    """
    Expects a django app module and returns an AppSyncInfo object about it.
    """
    app_name = app.__name__.rsplit('.', 1)[0]
    app_labels = set()
    schema_list = couchdbkit_handler.app_schema.values()
    for schema_dict in schema_list:
        for schema in schema_dict.values():
            app_module = schema.__module__.rsplit(".", 1)[0]
            if app_module == app_name and not schema._meta.app_label in app_labels:
                app_labels.add(schema._meta.app_label)

    designs = []
    for app_label in app_labels:
        if not app_label in couchdbkit_handler._databases:
            continue
        db = couchdbkit_handler.get_db(app_label)
        app_path = os.path.abspath(os.path.join(sys.modules[app.__name__].__file__, ".."))
        design_path = "%s/%s" % (app_path, "_design")
        if not os.path.isdir(design_path):
            design_path = None
        designs.append(DesignInfo(db=db, app_label=app_label, design_path=design_path))

    return AppSyncInfo(name=app_name, designs=designs)
