function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/xforms.js
    
    // for now incude all non-device-reports in this report
    if (doc["#doc_type"] == "XForm" && 
        doc["@xmlns"] != "http://code.javarosa.org/devicereport")
    {
        filled_on = get_form_filled_date(doc);
        duration = get_form_filled_duration(doc);
        if (filled_on && duration) {
            emit([doc.meta.clinic_id, doc.meta.user_id, new Date(filled_on.getFullYear(), filled_on.getMonth(), filled_on.getDate())], duration);
        }
    }
}