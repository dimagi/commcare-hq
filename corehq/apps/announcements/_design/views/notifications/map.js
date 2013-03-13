function(doc) {
    if(doc.base_doc === "Notification") {
        emit([doc.doc_type, doc.user], null);
    }
}
