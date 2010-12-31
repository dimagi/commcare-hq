function(doc) {
    //Basic emission of ALL audit events
    if(doc.base_type == 'AuditEvent') {
        //all audit events
        emit(doc._id, null);
    }
}