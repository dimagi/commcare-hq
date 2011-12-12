function(doc) {
    if (doc.doc_type == "XFormInstance" )
    {
        var submit_time = new Date(doc.received_on);
        if (submit_time) {
            emit([submit_time.getFullYear(), submit_time.getMonth()+1], doc.domain);
        }
    }
}