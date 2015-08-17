function(doc) {
    if (doc.doc_type == "PerformanceConfiguration") {
        // note: these constants are hard-coded against the models
        if (doc.schedule.interval === 'daily') {
            emit([doc.schedule.interval, doc.schedule.hour], null);
        } else if (doc.schedule.interval === 'weekly') {
            emit([doc.schedule.interval, doc.schedule.day_of_week, doc.schedule.hour], null);
        } else if (doc.schedule.interval === 'monthly') {
            emit([doc.schedule.interval, doc.schedule.day_of_month, doc.schedule.hour], null);
        }
    }
}
