function (doc) {
    if (doc.base_doc === "CustomDataFieldsDefinition") {
        emit([doc.domain, doc.doc_type], null);
    }
}
