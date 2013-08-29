function (doc) {
    if (doc.doc_type == 'XFormInstance'
        && doc.domain == 'pathfinder'
        && doc.xmlns.indexOf('reg') != -1
        && doc.form.meta)
    {
        emit([doc.domain, doc.form.meta.userID], null);
    }
}
