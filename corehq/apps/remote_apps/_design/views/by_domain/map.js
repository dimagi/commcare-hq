function(doc) {
    if(doc.doc_type == "RemoteApp") {
        emit(doc.domain, doc);
    }
}