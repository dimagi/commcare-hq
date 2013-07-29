function(doc) {
    if(doc.doc_type === "CommCareCase" && doc.type === "wisepill_device") {
        emit([doc.name], null);
    }
}
