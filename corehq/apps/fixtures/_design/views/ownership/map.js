function (doc) {
    if (doc.doc_type === 'FixtureOwnership') {
        emit([doc.domain, doc.owner_type + ' by data_item', doc.data_item_id], doc.owner_id);
        emit([doc.domain, 'data_item by ' + doc.owner_type, doc.owner_id], doc.data_item_id);
        emit([doc.domain, 'by data_item and ' + doc.owner_type, doc.data_item_id, doc.owner_id], null);
        emit([doc.domain, 'by data_item', doc.data_item_id], null);
    }
}