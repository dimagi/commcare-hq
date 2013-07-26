from couchdbkit import ResourceConflict
from couchdbkit.client import Database
from couchdbkit.ext.django.schema import Document
from django.conf import settings
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs

class DesignDoc(object):
    """Data structure representing a design doc"""
    
    def __init__(self, database, id):
        self.id = id
        self._doc = database.get(id)
        self.name = id.replace("_design/", "")
    
    @property
    def views(self):
        views = []
        if "views" in self._doc:
            for view_name, _ in self._doc["views"].items(): 
                views.append(view_name)
        return views

def get_db():
    """
    Get the couch database.
    """
    # this is a bit of a hack, since it assumes all the models talk to the same
    # db.  that said a lot of our code relies on that assumption.
    # this import is here because of annoying dependencies
    return Database(settings.COUCH_DATABASE)


def get_design_docs(database):
    design_doc_rows = database.view("_all_docs", startkey="_design/", 
                                    endkey="_design/zzzz")
    ret = []
    for row in design_doc_rows:
        ret.append(DesignDoc(database, row["id"]))
    return ret

def get_view_names(database):
    design_docs = get_design_docs(database)
    views = []
    for doc in design_docs:
        for view_name in doc.views:
            views.append("%s/%s" % (doc.name, view_name))
    return views

def iter_docs(database, ids, chunksize=100):
    for doc_ids in chunked(ids, chunksize):
        for doc in get_docs(database, keys=doc_ids):
            doc_dict = doc.get('doc')
            if doc_dict:
                yield doc_dict

def is_bigcouch():
    # this is a bit of a hack but we'll use it for now
    return 'cloudant' in settings.COUCH_SERVER_ROOT

def bigcouch_quorum_count():
    """
    The number of nodes to force an update/read in bigcouch to make sure
    we have a quorum. Should typically be the number of copies of a doc
    that end up in the cluster.
    """
    return (3 if not hasattr(settings, 'BIGCOUCH_QUORUM_COUNT')
            else settings.BIGCOUCH_QUORUM_COUNT)

def get_safe_write_kwargs():
    return {'w': bigcouch_quorum_count()} if is_bigcouch() else {}

def get_safe_read_kwargs():
    return {'r': bigcouch_quorum_count()} if is_bigcouch() else {}


class SafeSaveDocument(Document):
    """
    A document class that overrides save such that any time it's called in bigcouch
    mode it saves with the maximum quorum count (unless explicitly overridden).
    """
    def save(self, **params):
        if is_bigcouch() and 'w' not in params:
            params['w'] = bigcouch_quorum_count()
        return super(SafeSaveDocument, self).save(**params)

def safe_delete(db, doc_or_id):
    if not isinstance(doc_or_id, basestring):
        doc_or_id = doc_or_id._id
    db.delete_doc(doc_or_id, **get_safe_write_kwargs())

def apply_update(doc, update_fn, max_tries=5):
    """
    A function for safely applying a change to a couch doc. For getting around ResourceConflict
    errors that stem from the distributed cloudant nodes
    """
    tries = 0
    while tries < max_tries:
        try:
            update_fn(doc)
            doc.save()
            return doc
        except ResourceConflict:
            doc = doc.__class__.get(doc._id)
        tries+=1
    raise ResourceConflict("Document update conflict. -- Max Retries Reached")
