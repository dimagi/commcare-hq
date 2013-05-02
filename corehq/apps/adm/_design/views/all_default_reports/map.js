function (doc) {
    if (doc.doc_type === "ADMReport"
        && (!doc.domain || (doc.domain && doc.is_default))) {
        var entry = {
            name: doc.name,
            description: doc.description
        };
        if (doc.domain) {
            entry['domain'] = doc.domain;
        }
        emit(["defaults all slug", doc.reporting_section, doc.slug, doc._id], entry);
        if (doc.domain) {
            emit(["defaults domain slug", doc.domain, doc.reporting_section, doc.slug, doc._id], entry);
        } else {
            emit(["defaults global slug", doc.reporting_section, doc.slug, doc._id], entry);
        }
    }
}
