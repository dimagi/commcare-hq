function (doc) {
    if (doc.doc_type === "ADMReport") {
        var entry = {
            name: doc.name,
            description: doc.description,
            domain: doc.domain
        };
        if (doc.is_default) {
            emit(["defaults all", doc.reporting_section, doc.slug, doc._id], entry);
            if (doc.domain) {
                emit(["defaults domain", doc.domain, doc.reporting_section, doc.slug, doc._id], entry);
            } else {
                emit(["defaults global", doc.reporting_section, doc.slug, doc._id], entry);
            }
        } else if(doc.based_on_report) {
            emit(["custom", doc.domain, doc.based_on_report, doc.reporting_section, doc.slug, doc._id], entry);
        }
    }
}
