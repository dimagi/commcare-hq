function (doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/shared_funcs.js

    //urlpath by user date
    if (doc.base_type == 'AuditEvent') {
        //by username, and the events they do
        if (doc.doc_type == "NavigationEventAudit") {
            var event_date = parse_date(doc.event_date);
            //user event dates, emit to the class
            emit([doc.user, event_date.getUTCFullYear(), event_date.getUTCMonth() + 1, event_date.getUTCDate(), event_date.getUTCHours(), event_date.getUTCMinutes(), event_date.getUTCSeconds()], doc.request_path);
            emit([doc.user, event_date.getUTCFullYear(), event_date.getUTCMonth() + 1, event_date.getUTCDate(), event_date.getUTCHours(), event_date.getUTCMinutes(), event_date.getUTCSeconds()], {"request_path": doc.request_path, "status_code": doc.status_code});
        }
    }
}