function(doc) {
    //Basic emission of ALL audit events

    function parse_date(date_string) {
        if (!date_string) return new Date(1970,1,1);
        // hat tip: http://stackoverflow.com/questions/2587345/javascript-date-parse
        var parts = date_string.match(/(\d+)/g);
        // new Date(year, month [, date [, hours[, minutes[, seconds[, ms]]]]])
        return new Date(parts[0], parts[1]-1, parts[2]); // months are 0-based
    }

    if(doc.base_type == 'AuditEvent') {
        var date = parse_date(doc.event_date);
        //raw time
        //emit([date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()], null);
        //raw time, by event_class
        //emit([doc.event_class, date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()], null);
        //raw time, by user
        //emit([doc.user, date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()], null);
        //raw time, by user, event_class
        emit([doc.user, doc.event_class, doc.request_path, date.getFullYear(), date.getMonth() + 1, date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds()], null);
    }
}