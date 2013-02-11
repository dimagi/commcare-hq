function (doc) {
    if (doc.doc_type != 'FacilityRegistry') {
        return;
    }

    emit(doc._id, null);
}
