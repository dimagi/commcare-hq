function(doc) {
    var relevant_doc_types = [ "XFormInstance", "XFormError", "XFormDuplicate", 
                               "XFormDeprecated", "SubmissionErrorLog"];
    if (relevant_doc_types.indexOf(doc.doc_type) !== -1) {
        emit([doc.domain, "by_type", doc.doc_type, doc.received_on], null);
        emit([doc.domain, "by_date", doc.received_on, doc.doc_type], null);
    }
}