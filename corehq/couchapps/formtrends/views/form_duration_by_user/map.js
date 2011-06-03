function(doc) {
    function get_form_filled_date(xform_doc) {
        var meta = xform_doc.form.meta;
        if (meta && meta.timeEnd) return new Date(meta.timeEnd);
        if (meta && meta.timeStart) return new Date(meta.timeStart);
        return null;
    }
    
    function get_form_filled_duration(xform_doc) {
        // in milliseconds
        if (xform_doc.form.meta && xform_doc.form.meta.timeEnd && xform_doc.form.meta.timeStart) 
            return new Date(xform_doc.form.meta.timeEnd).getTime() - 
                    new Date(xform_doc.form.meta.timeStart).getTime(); 
        return null;
    }
    
    // for now incude all non-device-reports in this report
    if (doc.doc_type == "XFormInstance" &&
        doc.xmlns != "http://code.javarosa.org/devicereport")
    {
        var filled_on = get_form_filled_date(doc);
        var duration = get_form_filled_duration(doc);
        if (filled_on && duration) {
            emit([doc.domain, doc.form.meta.userID, filled_on], duration);
        }
    }
}