function(doc) { 
    if (doc["doc_type"] == "CPregnancy") {
        emit(doc.patient_id, doc);
    } 
}