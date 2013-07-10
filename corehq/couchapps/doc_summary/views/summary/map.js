function (doc) {
    if (doc.doc_type) {
        if (doc.domain) {
            emit(["by_type", doc.doc_type, doc.domain], null);
            emit(["by_domain", doc.domain, doc.doc_type], null);
        } else if (doc.domains) {
            for (var i = 0; i < doc.domains.length; i += 1) {
                var domain = doc.domains[i];
                emit(["by_type", doc.doc_type, domain], null);
                emit(["by_domain", domain, doc.doc_type], null);
            }
        }
    }
}
