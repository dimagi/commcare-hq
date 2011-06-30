function(doc) {
    if (doc.doc_type == "ExportSchema") {
        emit([doc.index, doc.seq], null);
    }
}