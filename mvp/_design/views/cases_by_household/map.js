function(doc) {
    var household_id = doc.household_head_health_id  || doc.household_head_id;
    if(doc.doc_type === "CommCareCase"
        && household_id ) {
        emit([doc.domain, doc.type, household_id, doc._id], 1);
    }
}