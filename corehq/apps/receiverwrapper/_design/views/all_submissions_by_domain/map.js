function(doc) {
    var relevant_doc_types = [ "XFormInstance", "XFormError", "XFormDuplicate", 
                               "XFormDeprecated", "SubmissionErrorLog"];
    if (relevant_doc_types.indexOf(doc.doc_type) !== -1) {
        // HACK: use the problem field to convert things to errors 
        // when emitting
        var doc_type = doc.doc_type;
        if (doc.doc_type === "XFormInstance" && doc.problem) {
            doc_type = "XFormError";
        }
        emit([doc.domain, "by_type", doc_type, doc.received_on], null);
        emit([doc.domain, "by_date", doc.received_on, doc_type], null);
    }
}