function (doc) {
    if (doc.doc_type === "RegistrationRequest") {
        emit(doc.new_user_username, null);
    }
}