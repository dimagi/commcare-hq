function (doc) {
    if (doc.base_doc === "DynamicIndicatorDefinition"
        && doc.doc_type !== "CombinedCouchViewIndicatorDefinition") {
        emit([doc.namespace, doc.domain, doc.slug, doc.version], 1);
    }
}
