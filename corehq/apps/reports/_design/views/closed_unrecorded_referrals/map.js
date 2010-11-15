function(doc) {
    /* Lists referral documents that are found within patients that are 
       closed and not recorded.
     */
    
    // CZUE: disable this old and broken view. 
    
    /*
    matches = function(referral) {
        return referral.closed && !referral.recorded;
    }
    
    // we only care about referrals in cases in patients
    if (doc.doc_type == "CPatient")
    {   
        for (i in doc.cases) {
            pat_case = doc.cases[i];
            for (j in pat_case.referrals) {
                case_ref = pat_case.referrals[j];
                if (matches(case_ref)) {
                    emit(case_ref._id, case_ref);
                }
            }   
        }
    }
    */
}