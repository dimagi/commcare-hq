function (doc) {
    if (doc.doc_type === "Invitation" && !doc.is_accepted) {
        emit([doc.email], null);
    }
}
