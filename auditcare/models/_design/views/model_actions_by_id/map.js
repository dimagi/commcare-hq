function(doc) {
    //basic emission of itemized audit events
    if (doc.base_type == 'AuditEvent') {
        if (doc.doc_type == "ModelActionAudit") {
            emit([doc.object_type, doc.object_uuid], doc.revision_id);
        }
    }
}