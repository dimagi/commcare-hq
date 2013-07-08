function (doc) {
    if (doc.doc_type === 'MobileIndicatorOwner') {
        emit([doc.domain, 'by_indicator_set_owner_type', doc.owner_type, doc.indicator_set_id], doc.owner_id);
        emit([doc.domain, 'by_owner', doc.owner_id], doc.indicator_set_id);
    }
}