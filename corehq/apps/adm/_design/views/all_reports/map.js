function (doc) {
    if (doc.doc_type === "ADMReport") {
        var entry = {
            name: doc.name,
            description: doc.description
        };
        if (!doc.project)
            emit(["defaults", doc.reporting_section, doc.slug, doc._id], entry);
        else
            emit(["projects", doc.project, doc.reporting_section, doc.slug, doc._id], entry);
    }
}