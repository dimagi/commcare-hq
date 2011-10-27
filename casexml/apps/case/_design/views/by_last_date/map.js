function(doc) {
    var DAY = 86400000;
    function mkdate(d) {
        return new Date(d.replace(/-/g, '/').replace('T', ' ').replace('Z', ''));
    }
    if (doc.doc_type == "CommCareCase" && !doc.closed) {
        emit([doc.domain, doc.type, doc.user_id, doc.modified_on], mkdate(doc.modified_on).getTime()/DAY);
        emit([doc.domain, {}, doc.user_id, doc.modified_on], mkdate(doc.modified_on).getTime()/DAY);
    }
}