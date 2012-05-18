function(doc){
    var relevant_doc_types = {
        "success": [ "XFormInstance" ],
        "error": ["XFormError", "XFormDuplicate", "XFormDeprecated", "SubmissionErrorLog"] 
    };
    for (var type in relevant_doc_types) {
        if (relevant_doc_types.hasOwnProperty(type)) {
            if (relevant_doc_types[type].indexOf(doc.doc_type) !== -1) {
                emit([doc.domain, type, doc.doc_type, doc.received_on], null);
            }
        }
    }
}