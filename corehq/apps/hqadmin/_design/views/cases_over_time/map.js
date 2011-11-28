function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.user_id ) {
        var d = new Date(doc.opened_on);
        emit([d.getFullYear(), d.getMonth()+1], null);
    }
}