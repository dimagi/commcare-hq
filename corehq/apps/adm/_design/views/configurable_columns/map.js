function (doc) {
    if (doc.config_doc === "ConfigurableADMColumn"
        && doc.doc_type !== "ConfigurableADMColumn") {
        if (doc.project === "")
            emit(["defaults", doc.doc_type, doc._id], 1);
        else
            emit(["projects", doc.project, doc.doc_type, doc._id], 1);
    }
}