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


    print "Migrating Audit Logs"

    chunk = 500
    start = 0
    seen_audits = 0
    while True:
        audit_iter = old_db.view('auditcare/all_events')#, skip=start, limit=chunk)
        if audit_iter.count() == 0:
            break

        for x in audit_iter.iterator():
            doc_id = x['id']
            doc = old_db.open_doc(doc_id)
            audit_db.save_doc(doc)
            old_db.delete_doc(doc_id)
            seen_audits += 1
        start += chunk

    print "completed %d audit migrations" % seen_audits

    print "Migrating couchlogs"
    start = 0
    seen_logs = 0
    while True:
        log_iter = old_db.view('couchlog/all_by_date')#, skip=start, limit=chunk)
        if log_iter.count() == 0:
            break
        for x in log_iter.iterator():
            doc_id = x['id']
            doc = old_db.open_doc(doc_id)
            log_db.save_doc(doc)
            old_db.delete_doc(doc_id)
            seen_logs += 1
        start += chunk

    print "completed %d log migrations" % seen_logs
