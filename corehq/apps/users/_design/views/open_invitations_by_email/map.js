function (doc) {
    if (doc.doc_type === "Invitation" && !doc.is_accepted && !doc.is_rejected) {
        emit([doc.email], null);
    }
}
