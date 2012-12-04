function (doc) {
    if (doc.base_doc === "CaseIndicatorDefinition" ||
        doc.base_doc === "FormIndicatorDefinition") {
        var class_path = doc.class_path + "." + doc.doc_type;
        emit(["namespace domain slug", doc.namespace, doc.domain, doc.slug, doc.version], class_path);
        if (doc.base_doc === "CaseIndicatorDefinition") {
            emit(["namespace domain case_type slug", doc.namespace, doc.domain, doc.case_type, doc.slug, doc.version], class_path);
        }
        if (doc.base_doc === "FormIndicatorDefinition") {
            emit(["namespace domain xmlns slug", doc.namespace, doc.domain, doc.xmlns, doc.slug, doc.version], class_path);
        }
    }
}
