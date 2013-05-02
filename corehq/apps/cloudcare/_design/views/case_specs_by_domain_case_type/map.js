function (doc) {
    if (doc.doc_type === 'CaseSpec') {
        emit([doc.domain, doc.case_type], null);
    }
}