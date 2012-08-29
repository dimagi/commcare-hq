function (doc) {
    if (!doc.is_snapshot && doc.original_doc) {
        emit(doc.original_doc, null);
    }
}