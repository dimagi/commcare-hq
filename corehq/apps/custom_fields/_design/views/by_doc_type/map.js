function (doc) {
    if (doc.base_doc === "CustomFieldsDefinition") {
        emit([doc.domain, doc.doc_type], null);
    }
}
