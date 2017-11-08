from __future__ import absolute_import
import logging
from collections import namedtuple

from couchdbkit import push, RequestFailed
from couchdbkit.exceptions import ResourceNotFound
import settings

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
        index_design_docs(db, docid, design_name_)


def index_design_docs(db, docid, design_name, wait=True):
    # found in the innards of couchdbkit
    view_names = list(db[docid].get('views', {}))
    if view_names:
        log.info('Triggering view rebuild')
        view = '%s/%s' % (design_name, view_names[0])
        while True:
            try:
                if wait:
                    list(db.view(view, limit=0))
                else:
                    list(db.view(view, limit=0, stale=settings.COUCH_STALE_QUERY))
            except RequestFailed as e:
                if 'timeout' not in e.message and e.status_int != 504:
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


DesignInfo = namedtuple('DesignInfo', ['db', 'app_label', 'design_path'])
