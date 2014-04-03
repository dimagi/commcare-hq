function (doc) {
    if (doc.doc_type === "PillowError" && doc.date_next_attempt) {
        emit([doc.date_next_attempt], null);
    }
}