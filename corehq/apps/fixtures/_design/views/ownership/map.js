function (doc) {
    if (doc.doc_type === 'FixtureOwnership') {
        emit([doc.owner_type + ' by data_item', doc.domain, doc.data_item_id], doc.owner_id);
        emit(['data_item by ' + doc.owner_type, doc.domain, doc.owner_id], doc.data_item_id);
        emit(['by data_item and ' + doc.owner_type, doc.domain, doc.data_item_id, doc.owner_id], null);
    }
}