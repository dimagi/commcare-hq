function(doc) {
    if (doc.doc_type == "XFormInstance" )
    {
        var submit_time = new Date(doc.received_on);
        if (submit_time) {
            emit([doc.domain, doc.form.meta.userID, submit_time.getUTCDay(), submit_time.getUTCHours()], 1);
        }
    }
}