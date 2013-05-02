function (doc) {
    if (doc.base_doc === "HQAnnouncement") {
        var emit_entry = {
            doc_type: doc.doc_type,
            title: doc.title,
        };
        emit(["all", doc.valid_until], emit_entry);
        emit(["type", doc.doc_type, doc.valid_until], emit_entry);
    }
}
