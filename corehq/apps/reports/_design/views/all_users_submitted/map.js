function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.form.meta.userID], {
            username: (doc.form.meta ? doc.form.meta.username : null)
        });
    }
}