function(doc) {
    if (doc.doc_type == "CommCareUser" )
    {
        var submit_time = new Date(doc.date_joined);
        if (submit_time) {
            emit([submit_time.getFullYear(), submit_time.getMonth()+1, submit_time.getDay()], 1);
        }
    }
}
