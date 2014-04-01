function (doc) {
    if (doc.doc_type === "PillowError") {
        emit(["attempts", doc.attempts], doc.attempts);
        emit(["pillow created", doc.pillow, doc.date_created], doc.attempts);
        emit(["pillow modified", doc.pillow, doc.date_last_error], doc.attempts);
        emit(["type created", doc.error_type, doc.date_created], doc.attempts);
        emit(["type modified", doc.error_type, doc.date_last_error], doc.attempts);
        emit(["created", doc.date_created], doc.attempts);
        emit(["modified", doc.date_last_error], doc.attempts);
    }
}