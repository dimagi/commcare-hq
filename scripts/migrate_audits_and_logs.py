from auditcare.models import AuditEvent
from casexml.apps.case.models import CommCareCase
from couchlog.models import ExceptionRecord

def run():
    #Migration script to move all audits and couchlogs to their own respective __auditcare and __couchlog couch databases

    from couchforms.models import XFormInstance
    old_db = XFormInstance.get_db()

    audit_db = AuditEvent.get_db()
    log_db = ExceptionRecord.get_db()

    print old_db
    print audit_db
    print log_db

    print "Migrating Audit Logs by bulk"
    chunk = 20


    def do_bulk_delete(view_name, destination_db):
        start = 0
        print "Doing bulk delete on %s" % view_name
        print "have destionation: %s" % destination_db
        print "have old: %s" % old_db
        while True:
            old_iter = old_db.view(view_name, skip=start, limit=chunk)
            if old_iter.count() == 0:
                break

            delete_doc_bunch = []

            for x in old_iter.iterator():
                doc_id = x['id']
                doc = old_db.open_doc(doc_id)
                #destination_db.save_doc(doc)
                delete_doc_bunch.append(doc)

            print "deleting %d docs from old db" % len(delete_doc_bunch)
            #old_db.delete_docs(delete_doc_bunch)
            start += len(delete_doc_bunch)

    print "Migrating Audits"
    do_bulk_delete('auditcare/all_events', audit_db)

    print "Migrating couchlogs"
    do_bulk_delete('couchlog/all_by_date', log_db)
