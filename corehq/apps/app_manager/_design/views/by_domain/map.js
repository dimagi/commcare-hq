function(doc){
    if(doc.doc_type == "XForm") {
        emit([doc.domain, doc.xmlns, doc.submit_time], doc);
    }
}