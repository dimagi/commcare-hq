function (doc) {
    if (doc.doc_type == 'XFormInstance'
        && doc.domain == 'pathfinder'
        && doc.form.meta)
    {
        var d = new Date(doc.form.meta.timeEnd);
        emit([doc.domain, doc.form.meta.userID, d.getUTCFullYear(), d.getUTCMonth() + 1], null);
    }
}