function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.xmlns, doc.received_on], doc);
    }
}