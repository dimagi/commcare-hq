function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/xforms.js
    
    if (doc.doc_type == "XFormInstance" )
    {
        filled_on = get_form_filled_date(doc);
        if (filled_on) {
            emit([doc.domain, doc.meta.user_id, filled_on.getDay(), filled_on.getHours()], 1);
        }
    }
}