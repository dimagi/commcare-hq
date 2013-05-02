function(doc) {
    if(doc.doc_type == "CommCareUser" || doc.doc_type == "WebUser") {
        emit(doc.phone_numbers[0], null);
    }
}
