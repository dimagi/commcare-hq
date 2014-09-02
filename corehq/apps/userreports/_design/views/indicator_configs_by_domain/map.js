function (doc) {
    if(doc.doc_type === "IndicatorConfiguration") {
        emit(doc.domain, null);
    }
}
