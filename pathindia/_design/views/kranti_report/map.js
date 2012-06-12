function(doc) {
    // !code util/pathindia.js

    if (doc.doc_type === 'XFormInstance'
        && doc.domain === 'pathindia'
        && doc.xmlns === "http://openrosa.org/formdesigner/A20E32BC-1CBF-4870-A448-C59957098A48" ){
        var info = doc.form.meta;
        var entry = new PathIndiaReport(doc);
        emit([doc.user_id, info.timeEnd], entry.data);
    }
}