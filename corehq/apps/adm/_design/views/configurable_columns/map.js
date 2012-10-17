function (doc) {
    if (doc.config_doc === "ConfigurableADMColumn"
        && doc.doc_type !== "ConfigurableADMColumn"
        && (!doc.domain || (doc.domain && doc.is_default)) ) {
        var entry = {
            name: doc.name,
            description: doc.description,
            domain: doc.domain,
            type: doc.doc_type
        };
        emit(["defaults all type", doc.doc_type, doc._id], entry);
        emit(["defaults all slug", doc.slug, doc._id], entry);
        if (doc.domain) {
            emit(["defaults domain type", doc.domain, doc.doc_type, doc._id], entry);
            emit(["defaults domain slug", doc.domain, doc.slug, doc._id], entry);
        } else {
            emit(["defaults global type", doc.doc_type, doc._id], entry);
            emit(["defaults global slug", doc.slug, doc._id], entry);
        }
    }
}
