function(doc) {
    if (doc.doc_type == "CommCareUser" )
    {
        var submit_time = new Date(doc.date_joined);
        if (submit_time) {
            emit([submit_time.getUTCFullYear(), submit_time.getUTCMonth()+1, submit_time.getUTCDay()], 1);
        }
    }
}
