function(doc) { 
    if (doc.doc_type == "CommCareCase") {
        emit(doc.case_id, doc);
    }
}