function(doc) {
    /* 
     * Mortality Register Report
     */
    
    // these lines magically import our other javascript files.  DON'T REMOVE THEM!
    // !code util/reports.js
    // !code util/xforms.js
    
    NAMESPACE = "http://cidrz.org/bhoma/mortality_register"
    
    if (xform_matches(doc, NAMESPACE) && false)
    {   
        report_values = [];
        /* this field keeps track of total forms */
        report_values.push(new reportValue(1,1,"total",true));
        
        enc_date = get_encounter_date(doc);
        
        /* Population Stats*/
        tot_pop = doc.num_adult_men + doc.num_adult_women + doc.num_under_five + doc.num_five_up;
        report_values.push(new reportValue(doc.num_adult_men, tot_pop, "% Adult Male",false,"Adult defined as older than 14 years"));
        report_values.push(new reportValue(doc.num_adult_women, tot_pop, "% Adult Female",false,"Adult defined as older than 14 years"));
        report_values.push(new reportValue(doc.num_under_five, tot_pop, "% Under Five"));
        
        /*Cycle through adult register to gather stats*/
        adult_male_deaths = 0;
        adult_female_deaths = 0;

    	adult_male_death_types = ['anaemia','diarrhea','hiv_aids','infection','hypertension','ext_bleeding','measles','pneumonia','malaria','tb','stroke','heart_problem','injuries','other'];
    	adult_deaths_by_type = adult_male_death_types.length;
    	female_death_types = ['anaemia','diarrhea','hiv_aids','infection','abortion','obstructed_labor','hypertension','ext_bleeding','measles','pneumonia','malaria','tb','stroke','heart_problem','injuries','other'];
    	female_deaths_by_type = female_death_types.length;
    	
        for (var adult_entry = 0; adult_entry < doc.adult_register.length; adult_entry++) {
        	/* Stats based on gender */
        	if (doc.gender == 'm') {
        		adult_male_deaths += 1;
        		for (i=0; i < adult_male_death_types.length; i++) {
        			if (doc.death_type == adult_male_death_types[i]) {
        				adult_deaths_by_type[i] += 1;
        			}
        		}	        	        		
        	} else if (doc.gender == 'f'){
        		adult_female_deaths += 1;
        		for (i=0; i < female_death_types.length; i++) {
        			if (doc.death_type == female_death_types[i]) {
        				female_deaths_by_type[i] += 1;
        			}
        		}
        	}
        	
        	/* Stats based on visits to clinic */
        	if (doc.visit_clinic == 'y') {
        		if (doc.death_location == 'home') {clinic_home += 1;}
        		else if (doc.death_location == 'clinic') {clinic_clinic += 1;}
        		else if (doc.death_location == 'hospital') {clinic_hospital += 1;}
        	} else if (doc.visit_clinic == 'n') {
        		if (doc.death_location == 'home') {no_clinic_home += 1;}
        		else if (doc.death_location == 'clinic') {no_clinic_clinic += 1;}
        		else if (doc.death_location == 'hospital') {no_clinic_hospital += 1;}
        	}
    	}    	

    	/*Child Register*/
    	ped_deaths = 0;
    	ped_death_types = ['still_birth','prolonged_labor','malformed','premature','infection','diarrhea','hiv_aids','measles','malaria','pneumonia','other'];
    	ped_deaths_by_type = new int[ped_death_types.length];
		
        for (var ped_entry = 0; ped_entry < doc.child_register.length; ped_entry++) {
    		ped_deaths += 1;
    		for (i=0; i < adult_male_death_types.length; i++) {
    			if (doc.death_type == adult_male_death_types[i]) {
    				adult_deaths_by_type[i] += 1;
    			}
    		}	        	        		
        	
        	/* Stats based on visits to clinic */
        	if (doc.visit_clinic == 'y') {
        		if (doc.death_location == 'home') {ped_clinic_home += 1;}
        		else if (doc.death_location == 'clinic') {ped_clinic_clinic += 1;}
        		else if (doc.death_location == 'hospital') {ped_clinic_hospital += 1;}
        	} else if (doc.visit_clinic == 'n') {
        		if (doc.death_location == 'home') {ped_no_clinic_home += 1;}
        		else if (doc.death_location == 'clinic') {ped_no_clinic_clinic += 1;}
        		else if (doc.death_location == 'hospital') {ped_no_clinic_hospital += 1;}
        	}
    	}    	

    	tot_deaths = adult_male_deaths + adult_female_deaths + ped_deaths;
    	report_values.push(new reportValue(adult_male_deaths, tot_deaths, "Adult Male Deaths"));
    	report_values.push(new reportValue(adult_female_deaths, tot_deaths, "Adult Female Deaths"));
    	report_values.push(new reportValue(ped_deaths, tot_deaths, "Under Five Deaths"));
    	
    	num_to_clinic = clinic_home + clinic_clinic + clinic_hospital + ped_clinic_home + ped_clinic_clinic + ped_clinic_hospital;
    	report_values.push(new reportValue((clinic_home+ped_clinic_home), num_to_clinic, "Went to Clinic, Died at Home"));
    	report_values.push(new reportValue((clinic_clinic+ped_clinic_clinic), num_to_clinic, "Went to Clinic, Died at Clinic"));
    	report_values.push(new reportValue((clinic_hospital+ped_clinic_hospital), num_to_clinic, "Went to Clinic, Died at Hospital"));
    	
    	num_no_clinic = no_clinic_home + no_clinic_clinic + no_clinic_hospital + ped_no_clinic_home + ped_no_clinic_clinic + ped_no_clinic_hospital;
    	report_values.push(new reportValue((no_clinic_home+ped_no_clinic_home), num_no_clinic, "Didn't go to Clinic, Died at Home"));
    	report_values.push(new reportValue((no_clinic_clinic+ped_no_clinic_clinic), num_no_clinic, "Didn't go to Clinic, Died at Clinic"));
    	report_values.push(new reportValue((no_clinic_hospital+ped_no_clinic_hospital), num_no_clinic, "Didn't go to Clinic, Died at Hospital"));    	
     	
    	for (j = 0; j < adult_deaths_by_type.length; j++) {
    		report_values.push(new reportValue(adult_deaths_by_type[j], adult_male_deaths, adult_male_death_types[j]));
    	}
    	for (k = 0; k < female_deaths_by_type; k++) {
    		report_values.push(new reportValue(female_deaths_by_type[k], adult_female_deaths, female_death_types[k]));
    	}
    	for (l = 0; l < ped_deaths_by_type; l++) {
    		report_values.push(new reportValue(ped_deaths_by_type[l], ped_female_deaths, ped_death_types[l]));
    	}
   
	    emit([enc_date.getFullYear(), enc_date.getMonth(), doc.meta.clinic_id], report_values);
	    
	     
    } 
}