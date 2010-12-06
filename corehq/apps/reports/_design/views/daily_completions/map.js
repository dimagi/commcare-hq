function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.form.Meta.TimeEnd.substring(0,10), doc.form.Meta.username], 1);
    }
}