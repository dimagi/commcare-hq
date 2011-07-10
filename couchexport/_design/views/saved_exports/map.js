function(doc) {
    if (doc.doc_type == "SavedExportSchema") {
        emit(doc.index, null);
    }
}