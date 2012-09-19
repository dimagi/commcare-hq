function(doc) {
    if (doc.doc_type === 'XFormInstance'
        && doc.domain === 'dca-malawi'
        && doc.xmlns === 'http://openrosa.org/formdesigner/7F8DAC38-27D9-446C-9A88-0DBE534C3956'){
        var u = doc.form.meta;
        var d = new Date(doc.form.meta.timeStart);

        emit([u.userID, d.getUTCMonth(), d.getUTCFullYear()], null);
    }
}
