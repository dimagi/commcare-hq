function (doc) {
    if (doc.doc_type === "FormLabelIndicatorDefinition") {
        emit([doc.namespace, doc.domain, doc.xmlns, doc.version], doc.slug);
    }
}
