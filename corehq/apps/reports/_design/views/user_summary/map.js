function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/xforms.js
    
    // for now incude all non-device-reports in this report
    if (doc.doc_type == "XFormInstance" )
    {
        emit([doc.domain, doc.form.Meta.user_id, get_encounter_date(doc), doc.xmlns], 1);
    }
}