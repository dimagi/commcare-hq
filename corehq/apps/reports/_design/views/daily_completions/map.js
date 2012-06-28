function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.form.meta.timeEnd.substring(0,10)+"T01:00:00Z", doc.form.meta.userID], 1);
    }
}