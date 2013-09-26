function(doc) {
    if(doc.doc_type === "FRIMessageBankMessage") {
        emit([doc.domain, doc.risk_profile], null);
    }
}
