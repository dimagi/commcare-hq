function(doc) {
    //Basic emission of login access events
    if(doc.base_type == 'AuditEvent' && doc.doc_type == 'AccessAudit' && doc.access_type == "login_failed") {
        //all audit events
        emit(['ip', doc.ip_address], {'event_date': doc.event_date, 'count': 1});
        emit(['ip_ua', doc.ip_address, doc.user_agent], {'event_date': doc.event_date, 'count': 1});
        emit(['user', doc.user], {'event_date': doc.event_date, 'count': 1});
    }
}