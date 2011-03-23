function(doc) {
    if(doc.doc_type == "JadJar") {
        emit(doc.build_number, null);
    }
}