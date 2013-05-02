function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id ) {
        var d = new Date(doc.opened_on);
        emit([d.getUTCFullYear(), d.getUTCMonth()+1], null);
    }
}