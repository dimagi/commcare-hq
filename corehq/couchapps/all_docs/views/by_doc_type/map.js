function (doc) {
    emit([doc.doc_type, doc._id], null);
}
