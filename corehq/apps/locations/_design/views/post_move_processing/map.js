function(doc) {
    if (doc.doc_type == "Location" && doc.flag_post_move) {
        emit([doc.domain], null);
    }
}
