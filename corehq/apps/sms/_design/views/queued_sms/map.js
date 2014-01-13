function(doc) {
    if (doc.doc_type === "SMSLog" && doc.processed === false && doc.datetime_to_process && !doc.error) {
    	emit(doc.datetime_to_process, null);
    }
}
