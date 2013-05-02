function (doc) {
    if (doc.doc_type === 'MobileAuthKeyRecord') {
        emit([doc.domain, doc.user_id, doc.valid], null);
    }
}