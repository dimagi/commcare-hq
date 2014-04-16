function (doc) {
    if (doc.doc_type === 'OpmReportSnapshot') {
        block = doc.block
        if (block == null) {
            block = ''
        }
        emit([doc.domain, doc.month, doc.year, doc.report_class, block], null);
    }
}