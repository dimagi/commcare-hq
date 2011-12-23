function(doc) {
    //Basic emission of ALL audit events
    // !code util/shared_funcs.js

    if(doc.base_type == 'AuditEvent') {
        var date = parse_date(doc.event_date);
        //raw by time
        emit([date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()], null);
    }
}
