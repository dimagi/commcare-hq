function(doc) { 
    if (doc.doc_type == "CPatient") {
        for (i in doc.cases) {
            pat_case = doc.cases[i];
            emit(pat_case._id, 1);
       }
    }
}