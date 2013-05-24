from couchdbkit import push
from couchdbkit.exceptions import ResourceNotFound


def sync_design_docs(db, design_dir, design_name, temp=None):
    design_name_ = '%s-%s' % (design_name, temp) if temp else design_name
    docid = "_design/%s" % design_name_
    push(design_dir, db, force=True, docid=docid)
    print "synced '%s' in couchdb" % design_name
    if temp:
        # found in the innards of couchdbkit
        try:
            view_names = db[docid].get('views', {}).keys()
            if len(view_names) > 0:
                print 'Triggering view rebuild'
                view = '%s/%s' % (design_name, view_names[0])
                list(db.view(view, limit=0))
        except Exception, ex:
            print "\tError trying to sync couchapp %s, but ignoring %s" % (docid, ex)


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