function(doc) {
    if(doc.doc_type === "WisePillDeviceEvent") {
        emit([doc.domain, doc.received_on], null);
    }
}
