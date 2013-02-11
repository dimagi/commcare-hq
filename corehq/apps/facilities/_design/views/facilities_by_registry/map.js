function (doc) {
    if (doc.doc_type != 'Facility') {
        return;
    }

    emit(doc.registry_id, doc._id);
}
