function(doc) {
    //Basic emission of login access events
    if(doc.base_type == 'AuditEvent' && doc.doc_type == 'AccessAudit') {
        //all audit events
        emit(['ip', doc.ip_address], [doc.event_date, doc.failures_since_start]);
        emit(['ip_ua', doc.ip_address, doc.user_agent], [doc.event_date, doc.failures_since_start]);
        emit(['user', doc.user], [doc.event_date, doc.failures_since_start]);
    }
}