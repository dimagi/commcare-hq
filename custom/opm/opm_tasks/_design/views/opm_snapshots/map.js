function (doc) {
    if (doc.doc_type === 'OpmReportSnapshot') {
        emit([doc.domain, doc.month, doc.year, doc.report_class, doc.block], null);
    }
}