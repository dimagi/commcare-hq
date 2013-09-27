function(doc) {
    if (doc.doc_type === 'CommCareCase' && doc.domain === "crs-remind" && (doc.type === "pregnant_mother" || doc.type === "baby")) {
        emit([doc.domain, doc.type, doc.block], 1);
    }
}