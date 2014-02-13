function(doc) {
    if (doc.doc_type == "DefaultConsumption") {
        var supply_point_type = (doc.type === 'supply-point') ? {} : doc.supply_point_type;
        emit([doc.domain, doc.product_id, supply_point_type, doc.supply_point_id], doc.default_consumption);
    }
}
