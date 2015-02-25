function(doc) {
    if (doc.doc_type == "CommCareUser" && doc.location_id) {
        emit([doc.location_id, doc._id], null);
    }
}
