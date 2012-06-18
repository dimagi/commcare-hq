function (doc) {
    if (doc.doc_type == 'Domain' && doc.is_snapshot && doc.published) {
        emit(doc.original_doc, null);
    }
}