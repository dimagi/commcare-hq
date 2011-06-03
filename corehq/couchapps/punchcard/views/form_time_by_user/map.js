function(doc) {
    
    function get_form_filled_date(xform_doc) {
	    var meta = xform_doc.form.meta;
	    if (meta && meta.timeEnd) return new Date(meta.timeEnd);
	    if (meta && meta.timeStart) return new Date(meta.timeStart);
	    return null;
	}
    
    if (doc.doc_type == "XFormInstance" )
    {
        var filled_on = get_form_filled_date(doc);
        if (filled_on) {
            emit([doc.domain, doc.form.meta.userID, filled_on.getDay(), filled_on.getHours()], 1);
        }
    }
}