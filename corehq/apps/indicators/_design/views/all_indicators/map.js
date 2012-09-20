function (doc) {
    if (doc.base_doc === "Indicator") {
        emit(["all", doc.domain, doc.slug, doc.version], doc.doc_type);
        var class_path = doc.class_path + "." + doc.doc_type;
        if (doc.doc_type === 'HistoricalIndicator')
            emit(["historical", doc.domain, doc.slug, doc.version], class_path);
        else
            emit(["active", doc.domain, doc.slug, doc.version], class_path);
    }
}