function (doc) {
    if (doc.base_doc === 'CouchUser') {
        emit(doc.django_id, null);
    }
}