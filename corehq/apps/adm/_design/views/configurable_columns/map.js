function (doc) {
    if (doc.config_doc === "ConfigurableADMColumn"
        && doc.doc_type !== "ConfigurableADMColumn") {
        var entry = {
            name: doc.name,
            description: doc.description,
            domain: doc.domain,
            type: doc.doc_type
        };
        if (doc.is_default) {
            emit(["defaults all type", doc.doc_type, doc._id], entry);
            emit(["defaults all slug", doc.slug, doc._id], entry);
            if (doc.domain) {
                emit(["defaults domain type", doc.domain, doc.doc_type, doc._id], entry);
                emit(["defaults domain slug", doc.domain, doc.slug, doc._id], entry);
            } else {
                emit(["defaults global type", doc.doc_type, doc._id], entry);
                emit(["defaults global slug", doc.slug, doc._id], entry);
            }
        } else if (doc.based_on_column) {
            emit(["custom type", doc.domain, doc.based_on_column, doc.doc_type, doc._id], entry);
            emit(["custom slug", doc.domain, doc.based_on_column, doc.slug, doc._id], entry);
        }
    }
}
