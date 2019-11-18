function(doc) {
    if (doc.is_daily_saved_export && doc.auto_rebuild_enabled) {
        emit([doc.last_accessed], null);
    }
}
