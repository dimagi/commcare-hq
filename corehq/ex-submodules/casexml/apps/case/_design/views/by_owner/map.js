function (doc) {
    if (doc.doc_type === 'CommCareCase') {
        var owner_id = doc.owner_id || doc.user_id;
        emit([owner_id, doc.closed], null);
    }
}