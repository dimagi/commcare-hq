function(doc) {
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/xforms.js
    
    // for now incude all non-device-reports in this report
    if (doc.doc_type == "XFormInstance" )
    {
        var device_ids = {};
        device_ids[doc.form.Meta.DeviceID] = null;
        emit([doc.domain, doc.form.Meta.username], {
            count: 1,
            last_submission_date:(get_encounter_date(doc)),
            username: doc.form.Meta.username,
            device_ids: device_ids,
        });
    }
}