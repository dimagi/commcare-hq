function(doc) {
    if(doc.doc_type == "VerifiedNumber") {
        emit(doc.phone_number, null);
    }
}
