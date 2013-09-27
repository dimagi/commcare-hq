function (doc) {
    if (doc.doc_type === 'LegacyWeeklyReport') {
        emit([doc.domain, doc.site, doc.week_end_date], null);
    }
}