function (doc) {
    if (doc.doc_type === "XFormInstance" && doc.xmlns) {
        emit([doc.domain, doc.app_id, doc.xmlns], null);
    }
}
