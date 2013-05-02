function(doc) {
    if (doc.doc_type == "XFormInstance" )
    {
        var submit_time = new Date(doc.received_on);
        if (submit_time) {
            emit([submit_time.getUTCFullYear(), submit_time.getUTCMonth()+1, doc.form.meta.userID], null);
        }
    }
}