function (doc) {
    if (doc.doc_type === "RegistrationRequest") {
        emit(doc.activation_guid, null);
    }
}