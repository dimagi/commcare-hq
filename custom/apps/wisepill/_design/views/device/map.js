function(doc) {
    if(doc.doc_type === "CommCareCase" && doc.type === "wisepill_device" && !doc.closed) {
        emit([doc.name], null);
    }
}
