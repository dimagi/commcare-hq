function (doc) {
    if (doc.doc_type === "ADMReport") {
        if (!doc.project)
            emit(["defaults", doc.reporting_section, doc.slug, doc._id], 1);
        else
            emit(["projects", doc.project, doc.reporting_section, doc.slug, doc._id], 1);
    }
}