function (doc) {
    if (doc.base_doc === "ADMColumn") {
        if (!(doc.config_doc === "ConfigurableADMColumn" && doc.domain)) {
            emit(["all", doc.doc_type, doc._id], 1);
            if (doc.returns_numerical)
                emit(["numerical", doc.doc_type, doc._id], {name: doc.name});
        }
    }
}
