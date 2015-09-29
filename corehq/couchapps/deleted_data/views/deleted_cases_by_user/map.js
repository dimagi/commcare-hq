function(doc) {
    if (doc.doc_type === 'CommCareCase-Deleted' && doc.user_id) {
        emit([(doc.owner_id || doc.user_id), doc.closed], null);
    }
}