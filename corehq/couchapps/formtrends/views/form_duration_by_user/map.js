function (doc) {
    function get_form_filled_duration(xform_doc) {
        // in milliseconds
        if (xform_doc.form && xform_doc.form.meta && xform_doc.form.meta.timeEnd && xform_doc.form.meta.timeStart) {
            return new Date(xform_doc.form.meta.timeEnd).getTime() -
                new Date(xform_doc.form.meta.timeStart).getTime();
        }
        return null;
    }
    
    // parse a date in yyyy-mm-dd format
	function parse_date(date_string) {
	    if (!date_string) return new Date(1970,1,1);
	    // hat tip: http://stackoverflow.com/questions/2587345/javascript-date-parse    
	    var parts = date_string.match(/(\d+)/g);
	    // new Date(year, month [, date [, hours[, minutes[, seconds[, ms]]]]])
	    return new Date(parts[0], parts[1]-1, parts[2]); // months are 0-based
	}
	    
    var duration, form_date, xmlns, userID, domain;

    // for now incude all non-device-reports in this report
    if (doc.doc_type === "XFormInstance" &&
            doc.xmlns !== "http://code.javarosa.org/devicereport" &&
            doc.xmlns !== "http://openrosa.org/user-registration") {
        duration = get_form_filled_duration(doc);
        if (duration) {
            domain = doc.domain;
            xmlns = doc.xmlns;
            userID = doc.form.meta.userID;
            form_date = parse_date(doc.received_on);
            emit(["dx", domain, form_date, xmlns], duration);
            emit(["udx", domain, userID, form_date, xmlns], duration);
            emit(["xdu", domain, xmlns, form_date, userID], duration);
            emit(["uxd", domain, userID, xmlns, form_date], duration);
        }
    }
}