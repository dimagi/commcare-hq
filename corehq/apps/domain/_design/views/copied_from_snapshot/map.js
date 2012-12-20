function (doc) {
    if (doc.doc_type == 'Domain' && !doc.is_snapshot && doc.copy_history.length > 0) {
        emit(doc.copy_history[doc.copy_history.length - 1], null);
    }
}