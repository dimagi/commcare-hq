function(doc) {
    /* Pregnancy Performance Indicator Report
     */
    
	// these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/reports.js
    // !code util/xforms.js
	HEALTHY_NAMESPACE = "http://cidrz.org/bhoma/pregnancy";
    SICK_NAMESPACE = "http://cidrz.org/bhoma/sick_pregnancy";
    
    if (xform_matches(doc, HEALTHY_NAMESPACE))
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
        #1. Pre-eclampsia screening and management
        #1a.Proportion of routine visits with Blood Pressure and Urinalysis results
        */
        
        vitals_recorded_num = Boolean(doc.blood_pressure && doc.urinalysis) ? 1 : 0;
        report_values.push(new reportValue(vitals_recorded_num, 1, "Vitals Recorded", false, "Blood Pressure recorded and Urinalysis section filled out.")); 
        
        /*
        #----------------------------------
        #3. Clinical Exam: record Fundal Height, Presentation, and Fetal Heart Rate
        */
        
        clinic_exam_num = Boolean(doc.fundal_height && doc.presentation && doc.fetal_heart_rate) ? 1 : 0;
        report_values.push(new reportValue(clinic_exam_num, 1, "Clinical Exam", false, "Fundal Height, Presentation, and Fetal Heart Rate recorded."));
        
        emit([enc_date.getFullYear(), enc_date.getMonth(), doc.meta.clinic_id], report_values); 
    } 
    else if (xform_matches(doc, SICK_NAMESPACE)) {
        
        /*
        #--------------------------------------------
        #9.  Drugs dispensed appropriately
        */
        
        drugs = doc.drugs;
        if (drugs["dispensed_as_prescribed"]) {
           drugs_appropriate_denom = 1;
           drugs_appropriate_num = exists(drugs["dispensed_as_prescribed"], "y") ? 1 : 0;
        } else {
           drugs_appropriate_denom = 0;
           drugs_appropriate_num = 0;
        }
        
        emit([enc_date.getFullYear(), enc_date.getMonth(), doc.meta.clinic_id], 
             [new reportValue(drugs_appropriate_num, drugs_appropriate_denom, "Drugs Dispensed Appropriately", false, "Original prescription dispensed.  Calculated from the 'Yes' under the form question, 'Was original prescription dispensed.'")]);
    } else if (doc["doc_type"] == "CPregnancy") {
        // this is where the aggregated data across pregnancies goes.
        report_values = [];
        /* this field keeps track of total pregnancies */
        first_visit_date = doc.first_visit_date
        
        report_values.push(new reportValue(1,1,"total",true));
        
        /*
        #----------------------------------- 
	    #1b.Proportion of (1a) above with abnormal results or Oedema who are 
	    #prescribed with Antihypertensives and Referred. 
		*/
	    
	    // here and below, if we don't have a follow date we don't emit anything
	    // that's fine, it just won't count towards either indicator (good or bad)
	    for (var i in doc.dates_preeclamp_treated) {
            treated_date = parse_date(doc.dates_preeclamp_treated[i]);
            emit([treated_date.getFullYear(), treated_date.getMonth(), doc.clinic_id], 
                 [new reportValue(1, 1, "Pre-eclampsia Managed",false,"Cases with Oedema or abnormal BP or protein in urine after 20 weeks GA who are prescribed with antihypertensives and referred.  Abnormal BP is SBP >= 140 or DBP >= 90.")]);
        }
        for (var i in doc.dates_preeclamp_not_treated) {
            treated_date = parse_date(doc.dates_preeclamp_not_treated[i]);
            emit([treated_date.getFullYear(), treated_date.getMonth(), doc.clinic_id], 
                 [new reportValue(0, 1, "Pre-eclampsia Managed",false,"Cases with Oedema or abnormal BP or protein in urine after 20 weeks GA who are prescribed with antihypertensives and referred.  Abnormal BP is SBP >= 140 or DBP >= 90.")]);
        }
        
		/*
        #-----------------------------------
	    #2. Danger signs followed up
	    #Assess if sick pregnancy form needs to be filled out
		*/
		
		for (var i in doc.dates_danger_signs_followed) {
            follow_date = parse_date(doc.dates_danger_signs_followed[i]);
            emit([follow_date.getFullYear(), follow_date.getMonth(), doc.clinic_id], 
                 [new reportValue(1, 1, "Danger Sign Follow Up",false,"Sick pregnancy form filled out if any Danger Sign apparent, a breech presentation after 27 weeks, or no fetal heart rate.")]);
		}
		for (var i in doc.dates_danger_signs_not_followed) {
            follow_date = parse_date(doc.dates_danger_signs_not_followed[i]);
            emit([follow_date.getFullYear(), follow_date.getMonth(), doc.clinic_id], 
                 [new reportValue(0, 1, "Danger Sign Follow Up",false,"Sick pregnancy form filled out if any Danger Sign apparent, a breech presentation after 27 weeks, or no fetal heart rate.")]); 
        }
		
		
		/*
	    #----------------------------------
	    #4. HIV Testing: Proportion of all pregnant women seen with HIV test done
		
		## Count per Pregnancy ID ##
		
		*/
		
		report_values.push(new reportValue(doc.hiv_test_done ? 1:0, 1, "HIV Test Done", false, "HIV Test Done during pregnancy."));
		
		/*
	    #----------------------------------
	    #5. NVP: Proportion of all women testing HIV-positive provided a dose of NVP on the 1st visit
	    */
		
		report_values.push(new reportValue(doc.got_nvp_when_tested_positive ? 1:0, 
		                                   doc.ever_tested_positive ? 1:0, "NVP", false, "Women testing HIV-positive provided with a does of NVP on the first visit they test HIV-positive."));
	    
		/*	
	    #-----------------------------------
	    #6. AZT: a.Proportion of all women testing HIV-positive provided AZT on ANY visit
	    #        b.Proportion of all women provided AZT who received it at their last visit
	    */
        
        got_azt_when_positive = doc.got_azt && doc.ever_tested_positive;
		report_values.push(new reportValue(got_azt_when_positive ? 1:0,
		                                   doc.ever_tested_positive ? 1:0, "AZT Given", false, "Women testing HIV-positive given a dose of AZT on any visit."));
		
		report_values.push(new reportValue(doc.got_azt_on_consecutive_visits ? 1:0,
		                                   doc.got_azt ? 1:0, "AZT Consecutively", false, "Women provided AZT who received it at both their current and previous visits."));	
		
	    /*	
	    #-----------------------------------
	    #7a.Proportion of all pregnant women seen with RPR test given on the 1st visit
		
		*/
		
		report_values.push(new reportValue(doc.rpr_given_on_first_visit ? 1:0,
		                                   1, "RPR 1st visit", false, "RPR test given on the first pregnancy visit."));
		
		/*
		#-----------------------------------
	    #7b.Proportion of all women testing RPR-positive provided a dose of penicillin
		*/
		
		report_values.push(new reportValue(doc.got_penicillin_when_rpr_positive ? 1:0, 
		                                   doc.tested_positive_rpr ? 1:0, "RPR+ Penicillin",false,"Women testing RPR-positive provided a dose of penicillin."));
		
	    /*
	    #7c. Proportion of all women testing RPR-positive whose partners are given penicillin 
	    #(does not include first visit that women discovers she is RPR positive)
		*/
		
		report_values.push(new reportValue(doc.partner_got_penicillin_when_rpr_positive ? 1:0,
		                                   doc.tested_positive_rpr ? 1:0, "RPR+ Partner",false,"Women testing RPR-positive whose partners are given penicillin (does not include the first visit discover RPR-positive)."));

		/*
	    #--------------------------------------------
	    #8. Fansidar:  Proportion of all pregnant women seen provided three doses of fansidar
		
		*/
		
		report_values.push(new reportValue(doc.got_three_doses_fansidar ? 1:0,
                                           1, "Fansidar",false,"3 doses of Fansidar given during pregnancy."));

        
	    first_visit_date = parse_date(doc.first_visit_date);
	    emit([first_visit_date.getFullYear(), first_visit_date.getMonth(), doc.clinic_id], report_values); 
    } 
}
