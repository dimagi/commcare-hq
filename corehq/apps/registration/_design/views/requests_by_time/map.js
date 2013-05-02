function (doc) {
    if (doc.doc_type === "RegistrationRequest") {
        emit(doc.request_time, null);
    }
}