function(doc) {
    //Basic readable emission of ALL audit events
    // !code util/shared_funcs.js

    if(doc.base_type == 'AuditEvent') {
        var date = parse_date(doc.event_date);
        //a raw event feed
        emit([date.getFullYear(),
            date.getMonth() + 1,
            date.getDate(),
            date.getHours(),
            date.getMinutes(),
            date.getSeconds(),
            doc.doc_type,
            doc.user ],
                null);
    }
}