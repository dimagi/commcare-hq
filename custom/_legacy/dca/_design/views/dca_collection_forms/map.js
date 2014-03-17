function(doc) {
    if (doc.doc_type === 'XFormInstance'
        && doc.domain === 'dca-malawi'
        && doc.xmlns === 'http://openrosa.org/formdesigner/53CCC67E-775F-4726-B187-BF558D40B679'){
        var u = doc.form.meta;
        var d = new Date(doc.form.meta.timeStart);

        emit([u.username, d.getUTCMonth(), d.getUTCFullYear()], null);
    }
}
