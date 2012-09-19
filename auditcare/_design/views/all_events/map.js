function(doc) {
    //Basic readable emission of ALL audit events
    // !code util/shared_funcs.js

    if(doc.base_type == 'AuditEvent') {
        var date = parse_date(doc.event_date);
        //a raw event feed
        emit([date.getUTCFullYear(),
            date.getUTCMonth() + 1,
            date.getUTCDate(),
            date.getUTCHours(),
            date.getUTCMinutes(),
            date.getUTCSeconds(),
            doc.doc_type,
            doc.user ],
                null);
    }
}