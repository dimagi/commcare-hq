// parse a date in yyyy-mm-dd format
function parse_date(date_string) {
    if (!date_string) return new Date(1970,1,1);
    // hat tip: http://stackoverflow.com/questions/2587345/javascript-date-parse
    var parts = date_string.match(/(\d+)/g);
    // new Date(year, month [, date [, hours[, minutes[, seconds[, ms]]]]])
    return new Date(parts[0], parts[1]-1, parts[2]); // months are 0-based
}

function get_date(xform_doc) {
    function get_date_string(xform_doc) {
        // check some expected places for a date
        var meta = xform_doc.form.meta;
        if (meta && meta.timeEnd) return meta.timeEnd;
        if (meta && meta.timeStart) return meta.timeStart;
        if (xform_doc.form.encounter_date) return xform_doc.form.encounter_date;
        return null;
    }
    return parse_date(get_date_string(xform_doc));
}
