function(doc) {
    if(doc.doc_type == "CommCareCase" && doc.type == 'child' ) {

        var definition = doc.computed_.mvp_indicators,
            namespace = "mvp_indicators",
            modified_on = doc.closed_on || doc.modified_on;

        log(definition);
        // Indicator 28 - Numerator
        if (definition.under_five)
            emit([namespace, "28_N", doc.domain, modified_on], {
                under_five: definition.under_five,
                rdt_received: definition.rdt_received
            });
    }
}