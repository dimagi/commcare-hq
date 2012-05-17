function(doc) {
    if(doc.doc_type == "MapsReportConfig") {
        emit([doc.domain], null);
    }
}