function(doc) {
    if(doc.doc_type === "XFormInstance") {
        if (doc.form.meta) {
            var entry = {
                completion_time: doc.form.meta.timeEnd,
                submission_time: doc.received_on,
                xmlns: doc.xmlns
            };
            emit(["user", doc.domain, doc.form.meta.userID, doc.received_on], entry);
            emit(["user form_type", doc.domain, doc.form.meta.userID, doc.xmlns, doc.received_on], entry);
        }
    }
}