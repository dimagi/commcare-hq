function (doc) {
    if (doc.doc_type === 'Review') {
        emit(doc.project_id, doc.rating || 0);
    }
}