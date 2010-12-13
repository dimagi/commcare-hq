function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.received_on], {
            time: doc.received_on,
            xmlns: doc.xmlns,
            username: doc.form.Meta.username
        });
    }
}