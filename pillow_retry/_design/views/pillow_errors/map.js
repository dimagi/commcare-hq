function (doc) {
    if (doc.doc_type === "PillowError") {
        emit(["created", doc.date_created], doc.total_attempts);
        emit(["modified", doc.date_last_attempt], doc.total_attempts);
        emit(["pillow created", doc.pillow, doc.date_created], doc.total_attempts);
        emit(["pillow modified", doc.pillow, doc.date_last_attempt], doc.total_attempts);
        emit(["type created", doc.error_type, doc.date_created], doc.total_attempts);
        emit(["type modified", doc.error_type, doc.date_last_attempt], doc.total_attempts);
        emit(["pillow type created", doc.pillow, doc.error_type, doc.date_created], doc.total_attempts);
        emit(["pillow type modified", doc.pillow, doc.error_type, doc.date_last_attempt], doc.total_attempts);
    }
}