function (doc) {
    if (doc.doc_type == 'XFormInstance'
        && doc.domain == 'pathfinder'
        && doc.xmlns.indexOf('ref_resolv') != -1
        && doc.form.meta
        && doc.form.case)
    {
        var d = new Date(doc.form.meta.timeEnd);
        emit([doc.form.case.case_id, d.getUTCFullYear(), d.getUTCMonth() + 1], null);
    }
}