function(doc) {
    // !code util/shared_funcs.js

    //basic emission of events by date, but filterable by the event itself.
    if(doc.doc_type == 'AccessAudit') {
        var date = parse_date(doc.event_date);
        //raw by time by event
        emit(['event', doc.doc_type, date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate(), date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()], null);
    }
}