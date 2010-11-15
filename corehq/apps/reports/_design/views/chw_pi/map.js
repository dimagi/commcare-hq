function(doc) {
    /* CHW Performance Indicator Report
     */
    
    // comment this half-baked report out.  it's killing the couch error log.
    if (doc["#doc_type"] == "XForm" && false)
    {   
        values = {};
        /* this field keeps track of total forms */
        values["total"] = true;
        new_case = doc.encounter_type == "new_case";
        values["followup_case"] = !new_case;
        enc_date = new Date(Date.parse(doc.encounter_date));
        
        /* TODO

        #CHW Performance Indicators

		#-----------------------------------
		#1. Follow Up Follow Through
		#(# Referrals from Follow Up Cases + # Follow Up Cases given Outcomes) / Total # of Follow Ups
		
		#-----------------------------------
		#2. Referrals that Visit Clinic
		#Proportion of new Referrals to go to the Clinic

        */    
	    emit([enc_date.getFullYear(), enc_date.getMonth(), doc.meta.clinic_id], values); 
    } 
}