function(doc) {
    //Basic emission of ALL audit events
    // !code util/shared_funcs.js

    if(doc.base_type == 'AuditEvent') {
        var date = parse_date(doc.event_date);
        //raw by time
        emit([date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate(), date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()], null);
    }
}
