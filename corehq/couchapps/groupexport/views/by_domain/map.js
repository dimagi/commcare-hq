function (doc) {
    if (doc.doc_type === "HQGroupExportConfiguration") {
        emit(doc.domain, null);
    }
}