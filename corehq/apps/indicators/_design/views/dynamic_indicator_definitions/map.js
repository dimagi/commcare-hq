function (doc) {
    if (doc.base_doc === "DynamicIndicatorDefinition") {
        var class_path = doc.class_path + "." + doc.doc_type;
        emit(["namespace domain slug", doc.namespace, doc.domain, doc.slug, doc.version], class_path);
    }
}
