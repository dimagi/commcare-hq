function(doc) {
    // !code util/shared_funcs.js

    //basic emission of events by date, but filterable by the event itself.
    if(doc.doc_type == 'AccessAudit') {
        var date = parse_date(doc.event_date);
        //raw by time by event
        emit(['event', doc.doc_type, date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()], null);
    }
}