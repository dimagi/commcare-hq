function(doc) {
    /* 
     * Under-five Performance Indicator Report
     */
    
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/reports.js
    // !code util/xforms.js
	
	NAMESPACE = "http://cidrz.org/bhoma/underfive"
    
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
		# 1. Height and Weight recorded 
		*/
		
        /* TODO: Figure out if last visit within a month */
        last_visit_within_a_month = function(doc) {
            return true;
        };
		vitals = doc.vitals;
		if (Boolean(new_case || !last_visit_within_a_month(doc))) {
			ht_wt_rec_denom = 1;
			ht_wt_rec_num = Boolean(vitals["height"] && vitals["weight"]) ? 1 : 0;
		} else {
			ht_wt_rec_denom = 0;
			ht_wt_rec_num = 0;
		}
		report_values.push(new reportValue(ht_wt_rec_num, ht_wt_rec_denom, "Height and weight recorded", false, "Height and Weight under Vitals section recorded. (Not counted against if already recorded for patient within last month or for a follow-up appointment after a sick visit)."));
        
        /* 
		#-----------------------------------
		# 2. Temperature, respiratory rate, and heart rate recorded 
		*/
		
        vitals_rec_num = Boolean(vitals["temp"] && vitals["resp_rate"] && vitals["heart_rate"]) ? 1 : 0;
		report_values.push(new reportValue(vitals_rec_num, 1, "Vitals recorded", false, "Temperature, Respiratory Rate, and Heart Rate under Vitals section recorded."));
		
        /*
		#-----------------------------------
		# 3. HIV test ordered appropriately
		*/
	    assessment = doc.assessment;
	    investigations = doc.investigations;
		
		var shows_hiv_symptoms = function(doc) {
	       return (exists(assessment["resp"],"sev_indrawing") ||
				   exists(assessment["resp"],"mod_fast_breath") ||
	               exists(assessment["diarrhea"],"sev_two_weeks") ||
	               exists(assessment["diarrhea"], "mod_two_weeks") ||
	               exists(assessment["diarrhea"], "mild_two_weeks") ||
	               exists(assessment["fever"], "sev_one_week") ||
				   exists(assessment["ear"], "mild_pus") ||
				   exists(assessment["malnutrition"], "sev_sd") ||
				   exists(assessment["malnutrition"], "mod_sd"));
	               
	    }
	    hiv = doc.hiv;
	    hiv_unknown = hiv["status"] == "unk";
		hiv_exposed = hiv["status"] == "exp";
		hiv_not_exposed = hiv["status"] == "unexp";
	    if ((hiv_unknown || hiv_exposed) || ((hiv_not_exposed || !hiv["status"]) && shows_hiv_symptoms(doc))) {
	       should_test_hiv = 1;
	       did_test_hiv = (exists(investigations["categories"], "hiv_rapid") || exists(investigations["categories"], "pcr")) ? 1 : 0;
	    } else {
	       should_test_hiv = 0;
           did_test_hiv = 0;
	    }
	    report_values.push(new reportValue(did_test_hiv, should_test_hiv, "HIV Test Ordered", false, "HIV Tests Ordered for patients with either Unknown or Exposed on their Under-5 card, or who have Not Exposed on their Under-5 card and exhibit symptoms with an asterisk (*). An HIV Test considered ordered if HIV Rapid or HIV DNA PCR ticked under investigations."));
	    
	    /*	    
		#-----------------------------------------------
	    #4. Weight for age assessed correctly
		*/
	    if (doc.zscore_calc_good === true || doc.zscore_calc_good == "true") {
           	wfa_assess_num = 1;
	    } else {
	    	wfa_assess_num = 0;
	    }
	    report_values.push(new reportValue(wfa_assess_num, 1, "Weight for age assessed", false, "Weight for Age under Nutritional Assessment correctly matches standard SD chart based on patient age, gender and weight.  If left blank, counted as poor management.")); 
        
        /* 
	    #--------------------------------------
	    #5. Low weight for age managed appropriately
		*/
		
		if (exists(assessment["malnutrition"],"sev_sd") || exists(assessment["malnutrition"],"mod_sd")) {
	       lwfa_managed_denom = 1;
		   lwfa_managed_num = doc.resolution == "closed" || "none" ? 0 : 1;
	    } else {
	       lwfa_managed_denom = 0;
	       lwfa_managed_num = 0;
	    }
		report_values.push(new reportValue(lwfa_managed_num, lwfa_managed_denom, "Low weight managed", false, "Follow-Up Visit section filled out if Low Weight for Age under Assessment ticked for either Severe or Moderate cases.  Counted as a correct Follow-up if either the Referral or Follow-Up boxes are checked."));      
	    
		/*    
	    #-----------------------------------------
	    #6. Fever managed appropriately
	    */
	    drugs_prescribed = doc.drugs_prescribed;
	    if (exists(assessment["categories"], "fever")) {
	       fever_managed_denom = 1;
	       /* If malaria test positive, check for anti_malarial*/
	       if (exists(investigations["rdt_mps"], "p") && drugs_prescribed) {
	       		/* check if severe */
	       		if (exists(assessment["fever"],"sev_one_week") || exists(assessment["fever"],"sev_stiff_neck")) {
       				fever_managed_num = check_drug_type(drugs_prescribed,"antimalarial","injectable");	
       			} else {
       			    fever_managed_num = check_drug_type(drugs_prescribed,"antimalarial"); 
       			}
	       /* If malaria test negative, check for antibiotic*/
	       } else if (exists(investigations["rdt_mps"], "n") && drugs_prescribed) {
	       		/* check if severe */
	       		if (exists(assessment["fever"],"sev_one_week") || exists(assessment["fever"],"sev_stiff_neck")) {
       				fever_managed_num = check_drug_type(drugs_prescribed,"antibiotic","injectable");	
       			} else {
       				fever_managed_num = check_drug_type(drugs_prescribed,"antibiotic");			       		
	       		}
	       } else {
	       		fever_managed_num = 0;
	       }
	    } else {
	       fever_managed_denom = 0;
           fever_managed_num = 0;
	    }
	    report_values.push(new reportValue(fever_managed_num, fever_managed_denom, "Fever Managed", false, "If Fever ticked under Assessment, make sure the proper drugs are Prescribed. If a severe symptom is indicated, the drug formulation should be injectable.  If tested positive for Malaria, an Anti-malarial should be prescribed, otherwise an Antibiotic should be prescribed.")); 
        
	    /*
	    #----------------------------------------
	    #7. Diarrhea managed appropriately
	    */
	    drugs = doc.drugs;
	    
	    need_treatment = exists(assessment["diarrhea"],"sev_dehyd") || exists(assessment["diarrhea"],"mod_dehyd");
	    if (exists(assessment["categories"],"diarrhea") && need_treatment) {
	       diarrhea_managed_denom = 1;
	       /* Check dehydration level */
	       if (exists(assessment["diarrhea"],"sev_dehyd") && drugs_prescribed) {
	       		if (exists(investigations["stool"],"blood") || exists(investigations["stool"],"pus")) {
	       			diarrhea_managed_num = check_drug_type(drugs_prescribed,"antibiotic") && check_drug_name(drugs_prescribed,"ringers_lactate");
	       		} else {
	       			diarrhea_managed_num = check_drug_name(drugs_prescribed,"ringers_lactate");;
	       		}
	       } else if (exists(assessment["diarrhea"],"mod_dehyd") && drugs_prescribed) {
	       		if (exists(investigations["stool"],"blood") || exists(investigations["stool"],"pus")) {
	       			diarrhea_managed_num = check_drug_type(drugs_prescribed,"antibiotic") && check_drug_name(drugs_prescribed,"ors");;
	       		} else {
	       			diarrhea_managed_num = check_drug_name(drugs_prescribed,"ors");;
	       		}
	       } else {
	       		diarrhea_managed_num = 0;
	       }
	    } else {
	       diarrhea_managed_denom = 0;
           diarrhea_managed_num = 0;
	    }
	    report_values.push(new reportValue(diarrhea_managed_num, diarrhea_managed_denom, "Diarrhea Managed", false, "If Diarrhea ticked under Assessment, verify drugs prescribed correctly.  Moderate Dehydration should be prescribed ORS.  Severe Dehydration should be prescribed Ringers lactate.  If Blood or Pus indicated in Stool, verify anti-biotic prescribed in addition to rehydration drugs."));    
        
	    /*
	    #----------------------------------------
	    #8. RTI managed appropriately 
		*/
		if (exists(assessment["categories"],"resp") && exists(assessment["categories"],"fever")) {
	       rti_managed_denom = 1;
	       /* If resp and fever ticked in assessment, check for anitbiotic (injectable for severe fever)) */
	       if (drugs_prescribed && (exists(assessment["fever"],"sev_one_week") || exists(assessment["fever"],"sev_stiff_neck"))) {
	       		rti_managed_num = check_drug_type(drugs_prescribed,"antibiotic","injectable");
	       } else if (drugs_prescribed){
	       		rti_managed_num = check_drug_type(drugs_prescribed,"antibiotic");
	       } else {
	       		rti_managed_num = 0;
	       }
	    } else {
	       rti_managed_denom = 0;
           rti_managed_num = 0;
	    }
	    report_values.push(new reportValue(rti_managed_num, rti_managed_denom, "RTI Managed", false, "If Cough/Difficulty Breathing and Fever are ticked under Assessment, verify drugs prescribed correctly.  If both are ticked, an Antibiotic should be prescribed.  If a severe Fever symptom is indicated the formulation of the antibiotic prescribed should be injectable.")); 
		
	    /*
	    #-------------------------------------------
	    #9. Hb done if pallor detected
		*/
		
	    if (exists(doc.general_exam,"severe_pallor") || exists(doc.general_exam,"mod_pallor")) {
	       hb_if_pallor_denom = 1;
	       hb_if_pallor_num = exists(investigations["categories"], "hb_plat") ? 1 : 0;
	    } else {
	       hb_if_pallor_denom = 0;
	       hb_if_pallor_num = 0;
	    }
		report_values.push(new reportValue(hb_if_pallor_num,hb_if_pallor_denom,"Hb done if pallor", false, "If either Moderate or Severe Pallor is ticked under the Physical Exam, verify Hgb ticked under Investigation."));
        
	    /*
	    #-------------------------------------------
	    #10. Proportion of patients followed up
	    #10a.Proportion of forms with Case Closed or Follow-Up recorded   
		*/
		
		followup_recorded_num = doc.resolution == "none" ? 0 : 1;
		report_values.push(new reportValue(followup_recorded_num, 1, "Patients followed up", false, "Case Closed, Follow-Up, or Referral ticked."));
        
	    /*
	    #10b.Verify Case Closed and Outcome given for all forms that are Follow-Up Appointments  
		*/
		
	    if (!new_case) {
	       outcome_recorded_denom = 1;
	       outcome_recorded_num = Boolean(exists(doc.resolution,"closed") && doc.outcome) ? 1 : 0;
	    } else {
	       outcome_recorded_denom = 0;
	       outcome_recorded_num = 0;
	    }
		report_values.push(new reportValue(outcome_recorded_num, outcome_recorded_denom, "Review cases managed", false, "Case Closed ticked and Outcome selected for all Review Cases."));
		
	    /*
	    #11.  Drugs dispensed appropriately
		*/

		drugs = doc.drugs;
		if (drugs["dispensed_as_prescribed"]) {
	       drugs_appropriate_denom = 1;
	       drugs_appropriate_num = exists(drugs["dispensed_as_prescribed"], "y") ? 1 : 0;
	    } else {
	       drugs_appropriate_denom = 0;
	       drugs_appropriate_num = 0;
	    }
		report_values.push(new reportValue(drugs_appropriate_num, drugs_appropriate_denom, "Drugs dispensed appropriately", false, "Original prescription dispensed.  Calculated from the 'Yes' under the form question, 'Was original prescription dispensed.'")); 
        
	    emit([enc_date.getFullYear(), enc_date.getMonth(), doc.meta.clinic_id], report_values); 
    } 
}