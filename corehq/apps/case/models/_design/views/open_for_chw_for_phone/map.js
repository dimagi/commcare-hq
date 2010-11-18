
function(doc) { 
    if (doc.doc_type == "CPatient") {
        for (i in doc.cases) {
            pat_case = doc.cases[i];
            if (!pat_case.closed && pat_case.send_to_phone) {
                emit([doc.address.clinic_id, doc.address.zone], pat_case);
            }
        }
    }
}