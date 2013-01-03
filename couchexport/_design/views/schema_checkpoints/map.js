function(doc) {
    if (doc.doc_type == "ExportSchema") {
        emit(['by_timestamp', doc.index, doc.timestamp], null);
        emit(['by_seq', doc.index, doc.seq], null);
    }
}