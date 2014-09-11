function (doc) {
    if (doc.base_doc === "CustomDataFieldsDefinition") {
        emit([doc.domain, doc.field_type], null);
    }
}
