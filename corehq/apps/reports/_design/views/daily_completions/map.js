function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.form.meta.TimeEnd.substring(0,10), doc.form.meta.username], 1);
    }
}