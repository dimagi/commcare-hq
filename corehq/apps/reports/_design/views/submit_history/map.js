function(doc) {
    if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.form.meta.userID, doc.received_on], {
            time: doc.received_on,
            xmlns: doc.xmlns,
            username: doc.form.meta.username,
            app_id: doc.app_id
        });
    }
}