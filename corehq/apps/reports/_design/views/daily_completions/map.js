function(doc) {
    if(doc.doc_type === "XFormInstance") {
        emit([doc.domain, doc.form.meta.timeEnd], {
            user_id: (doc.form.meta ? doc.form.meta.userID : null),
            username: (doc.form.meta ? doc.form.meta.username : null)
        });
    }
}