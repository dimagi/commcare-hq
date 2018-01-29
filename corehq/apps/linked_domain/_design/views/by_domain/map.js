function (doc) {
    if (doc.doc_type === 'DomainLink') {
        emit([doc.master_domain, 'master', doc.last_pull], null);
        emit([doc.linked_domain, 'linked', doc.last_pull], null);
    }
}
