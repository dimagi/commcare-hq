function(doc) {
    if(doc.doc_type === "CaseActivityReportCache") {
        emit(doc.domain, {});
    }
}