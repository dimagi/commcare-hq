function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/xforms.js
    
    // for now incude all non-device-reports in this report
    if (doc["#doc_type"] == "XForm" && 
        doc["@xmlns"] != "http://code.javarosa.org/devicereport")
    {
        filled_on = get_form_filled_date(doc);
        if (filled_on) {
            emit([doc.meta.clinic_id, doc.meta.user_id, filled_on.getDay(), filled_on.getHours()], 1);
        }
    }
}