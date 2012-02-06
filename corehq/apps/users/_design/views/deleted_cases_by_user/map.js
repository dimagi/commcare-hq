function(doc) {
    if (doc.doc_type === 'CommCareCase-Deleted' && doc.user_id) {
        emit([doc.user_id, doc.closed], null);
    }
}