function(doc) {
    /* 
     * Adult Performance Indicator Report
     */
    
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/reports.js
    // !code util/xforms.js
    
    NAMESPACE = "http://cidrz.org/bhoma/general"
    
    if (xform_matches(doc, NAMESPACE))
    {   
        report_values = [];
        /* this field keeps track of total forms */
        report_values.push(new reportValue(1,1,"total",true));
        
        new_case = doc.encounter_type == "new_case" ? 1 : 0;
        report_values.push(new reportValue(new_case, 1, "new_case", true));
        
        followup_case = doc.encounter_type == "new_case" ? 0 : 1;
        report_values.push(new reportValue(followup_case, 1, "followup_case", true));
        
        
        enc_date = get_encounter_date(doc);

        /*
        #-----------------------------------
        #1. Blood Pressure recorded
        */
        
        vitals = doc.vitals;        
        bp_recorded_num = Boolean(vitals["bp"]) ? 1 : 0;
        report_values.push(new reportValue(bp_recorded_num, 1, "Blood Pressure Recorded", false, "'Blood Pressure' recorded under Vitals section.")); 
        
        /*
        #-----------------------------------
	    #2. TB managed appropriately
	    */
	    
	    assessment = doc.assessment;
	    investigations = doc.investigations;
	    if (exists(assessment["categories"],"resp") && exists(assessment["resp"],"mod_cough_two_weeks")) {
	       tb_managed_denom = 1;
	       tb_managed_num = exists(investigations["categories"], "sputum") ? 1 : 0;
	    } else {
	       tb_managed_denom = 0;
	       tb_managed_num = 0;
	    }
	    report_values.push(new reportValue(tb_managed_num, tb_managed_denom, "TB Managed", false, "If the 'Cough > 2 weeks' symptom under the Cough/Difficulty Breathing assessment is ticked, 'Sputum' under Investigation section should also be ticked.")); 
	
	    /*
	    #-----------------------------------
	    #3. Malaria managed appropriately
	    */       
        drugs_prescribed = doc.drugs_prescribed;
	    if (exists(doc.danger_signs, "fever")) {
	       malaria_managed_denom = 1;
	       /* If malaria test positive, check for anti_malarial, otherwise anti_biotic */
	       if (exists(investigations["rdt_mps"], "p") && drugs_prescribed) {
       			malaria_managed_num = check_drug_type(drugs_prescribed,"antimalarial");	
	       } else if (exists(investigations["rdt_mps"], "n") && drugs_prescribed) {
       			malaria_managed_num = check_drug_type(drugs_prescribed,"antibiotic");			       		
	       } else {
	       		malaria_managed_num = 0;
	       }
	    } else {
	       malaria_managed_denom = 0;
           malaria_managed_num = 0;
	    }
	    report_values.push(new reportValue(malaria_managed_num, malaria_managed_denom, "Malaria Managed", false, "If 'Fever > 39deg' ticked under Danger Signs, verify Prescriptions match the Malaria investigation outcome.  If tested positive for Malaria, an Anti-malarial should be prescribed, otherwise an Antibiotic should be prescribed.")); 

        /*
	    #----------------------------------------------
	    #4. HIV test ordered appropriately
	    # Check if HIV symptoms present
	    */
	    
	    var shows_hiv_symptoms = function(doc) {
	       return (exists(doc.phys_exam_detail, "lymph") || 
	               exists(assessment["resp"],"sev_fast_breath") ||
				   exists(assessment["resp"],"mod_cough_two_weeks") ||
	               exists(assessment["categories"],"weight") ||
	               exists(assessment["categories"], "anogen") ||
	               exists(assessment["dischg_abdom_pain"], "sev_mass") ||
	               exists(assessment["mouth_thrush"], "mod_ulcers") ||
	               exists(assessment["mouth_throat"], "mod_ulcers"));
	               
	    }
	    hiv_not_tested = doc.hiv_result == "nd";
	    if ((hiv_not_tested || !doc.hiv_result) && shows_hiv_symptoms(doc)) {
	       should_test_hiv = 1;
	       did_test_hiv = exists(investigations["categories"], "hiv_rapid") ? 1 : 0;
	    } else {
	       should_test_hiv = 0;
           did_test_hiv = 0;
	    }
	    report_values.push(new reportValue(did_test_hiv, should_test_hiv, "HIV Test Ordered", false, "HIV tests ordered for patients with 'HIV Test Not Done' under Past Medical History ticked who also exhibit any symptoms with an asterisk (*).  An HIV Test is considered ordered if 'HIV Rapid' ticked under investigations."));
		    
		/*
	    #----------------------------------------------
	    #5. Drugs dispensed appropriately
	    */
		
		drugs = doc.drugs;
		if (drugs["dispensed_as_prescribed"]) {
	       drugs_appropriate_denom = 1;
	       drugs_appropriate_num = exists(drugs["dispensed_as_prescribed"], "y") ? 1 : 0;
	    } else {
	       drugs_appropriate_denom = 0;
	       drugs_appropriate_num = 0;
	    }
		report_values.push(new reportValue(drugs_appropriate_num, drugs_appropriate_denom, "Drugs Dispensed Appropriately", false, "Original prescription dispensed.  Calculated from the 'Yes' under the form question, 'Was original prescription dispensed.'")); 
    
	    emit([enc_date.getFullYear(), enc_date.getMonth(), doc.meta.clinic_id], report_values); 
    } 
}