function(doc) {
    if(doc.doc_type == "JadJar") {
        emit(doc.version, doc);
    }
}