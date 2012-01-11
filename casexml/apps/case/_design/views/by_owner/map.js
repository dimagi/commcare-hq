function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        if (doc.owner_id) {
            emit([doc.owner_id, doc.closed], null);
        } else {
            emit([doc.user_id, doc.closed], null);
        }
    }
}