function(doc){
    if (doc.doc_type === 'OrgRequest') {
        emit([doc.organization, doc.domain, doc.requested_by, doc.requested_on],null);
    }
}