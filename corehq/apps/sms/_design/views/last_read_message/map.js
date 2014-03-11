function(doc) {
    if(doc.doc_type === "LastReadMessage") {
        emit(["by_user", doc.domain, doc.read_by, doc.contact_id], null);
        emit(["by_anyone", doc.domain, doc.contact_id, doc.message_timestamp], null);
    }
}
