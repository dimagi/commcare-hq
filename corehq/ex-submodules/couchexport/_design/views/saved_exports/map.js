function(doc) {
    if (doc.doc_type == "SavedBasicExport") {
        emit(doc.configuration.index, doc.last_updated);
    }
}