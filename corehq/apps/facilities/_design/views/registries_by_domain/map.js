function (doc) {
    if (doc.doc_type != 'FacilityRegistry') {
        return;
    }

    emit(doc.domain, null);
}
