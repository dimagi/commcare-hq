function (doc) {
    if(doc.doc_type === "RegistryDataSourceConfiguration") {
        emit([doc.domain, doc.registry_slug], {
            is_deactivated: doc.is_deactivated,
            globally_accessible: doc.globally_accessible,
        });
    }
}
