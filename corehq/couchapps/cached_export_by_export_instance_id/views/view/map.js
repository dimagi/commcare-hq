function(doc) {
    if (doc.doc_type == "CachedExport") {
        emit(doc.export_instance_id, doc.last_updated);
    }
}
