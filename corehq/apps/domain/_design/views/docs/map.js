function (doc) {
    // !code util/doc_utils.js

    var i,
        date,
        domains;
    if (doc.doc_type) {
        date = get_date(doc);
        domains = get_domains(doc);
        for (i = 0; i < domains.length; i += 1) {
            emit([domains[i], doc.doc_type, date], null);
        }
    }
}