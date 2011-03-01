function(doc) {
    //Basic emission of ALL audit events
    if(doc.base_type == 'AuditEvent' && doc.doc_type == 'AccessAudit') {
        //all audit events
        emit(doc._id, null);
    }
}