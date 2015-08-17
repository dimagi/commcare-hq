function(doc) {
    if (doc.doc_type == "PerformanceConfiguration")
    {
        emit([doc.schedule.interval, doc.schedule.hour, doc.schedule.day_of_week, doc.schedule.day_of_month], null);
    }
}
