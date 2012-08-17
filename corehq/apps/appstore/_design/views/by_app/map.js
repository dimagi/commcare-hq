function (doc) {
    if (doc.doc_type === 'Review') {
        emit(doc.original_doc, doc.rating || 0);
    }
}