function(doc) {
    if (doc.doc_type == "PerformanceConfiguration")
    {
        emit([doc.interval, doc.hour, doc.day_of_week, doc.day_of_month], null);
    }
}
