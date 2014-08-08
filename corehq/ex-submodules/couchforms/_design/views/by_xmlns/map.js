function (doc) {
    if(doc['doc_type'] == "XFormInstance") {
        emit(doc.xmlns, null);
    }
}
