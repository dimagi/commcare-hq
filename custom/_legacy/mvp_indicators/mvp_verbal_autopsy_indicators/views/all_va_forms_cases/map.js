function (doc) {
    // !code util/mvp.js
    if (isVerbalAutopsyNeonateForm(doc) ||
        isVerbalAutopsyChildForm(doc) ||
        isVerbalAutopsyAdultForm(doc)) {

        var indicators = get_indicators(doc),
    		indicator_keys = {},
    		medical_reason = "",
    		delay_treatment_reason = "",
            close_date = new Date(doc.form.meta.timeEnd);

        indicator_keys["case_id"] = get_case_id(doc);

        //Death Dates
        if (indicators.date_of_termination && indicators.date_of_termination.value) {
        	var death_date = new Date(indicators.date_of_termination.value);
            indicator_keys["death_month"] = death_date.getUTCMonth();
            indicator_keys["death_year"] = death_date.getUTCFullYear();
        }
        if (indicators.age_category && indicators.age_category.value) {
            indicator_keys["age_category"] = indicators.age_category.value;
        }
        if (indicators.last_chw_visit && indicators.last_chw_visit.value) {
            indicator_keys["last_chw_visit"] = indicators.last_chw_visit.value;
        }
        if (indicators.received_treatment && indicators.received_treatment.value) {
           	var received_treatment = indicators.received_treatment.value;
            if ( received_treatment == 1){
                indicator_keys["received_treatment"] = "Yes";
            }
            if ( received_treatment == 2){
                indicator_keys["received_treatment"] = "No";
            }
                if ((received_treatment == 2 || received_treatment == 90) &&
                	indicators.no_treatment_reason && indicators.no_treatment_reason.value) {
                	var reason = indicators.no_treatment_reason.value;
	                if ( reason == 1){
	                	delay_treatment_reason += "Personal/religious objection <br>";
	                }
	                if ( reason == 2){
	                	delay_treatment_reason += "No means of transport <br>";
	                }
	                if ( reason == 3){
	                	delay_treatment_reason += "No money for transport <br>";
	                }
	                if ( reason == 4){
	                	delay_treatment_reason += "No phone to call transport <br>";
	                }
	                if ( reason == 5){
	                	delay_treatment_reason += "No money for phone to call transport <br>";
	                }
	                if ( reason == 6){
	                	delay_treatment_reason += "Transport was too late <br>";
	                }
	                if ( reason == 7){
	                	delay_treatment_reason += "No money to pay for consult <br>";
	                }
	                if ( reason == 8){
	                	delay_treatment_reason += "No money to pay for drugs <br>";
	                }
	                if ( reason == 90){
	                	delay_treatment_reason += "Don't know <br>";
	                }
	                if ( reason == 96){
	                	delay_treatment_reason += "Other <br>";
	                }

					indicator_keys["no_treatment_reason"] = delay_treatment_reason;

                }
            }
            //deathplace
            if (indicators.death_place && indicators.death_place.value) {
                var death_place = indicators.death_place.value;
                if (death_place == 11) {
                    indicator_keys["death_place"] = "Hospital";
                }
                if (death_place == 12) {
                    indicator_keys["death_place"] = "Health clinic/post";
                }
                if (death_place == 14) {
                    indicator_keys["death_place"] = "Home";
                }
                if (death_place == 13) {
                    indicator_keys["death_place"] = "On route";
                }
                if (death_place == 90) {
                    indicator_keys["death_place"] = "Dont Know";
                }
            }

        //Treatment from
        if (isVerbalAutopsyNeonateForm(doc)) {
			if (indicators.birth_asphyxia && indicators.birth_asphyxia.value == 1) {
                medical_reason += "Birth asphyxia <br>";
            }
            if (indicators.birth_trauma && indicators.birth_trauma.value == 1) {
                medical_reason += "Birth trauma  <br>";
            }
            if (indicators.congenital_abnormality && indicators.congenital_abnormality.value == 1) {
                medical_reason += "Congenital abnormality <br>";
            }
            if (indicators.neonate_diarrhea_dysentery && indicators.neonate_diarrhea_dysentery.value == 1) {
                medical_reason += "Diarrhea/Dysentery <br>";
            }
            if (indicators.lowbirthweight_malnutrition_preterm && indicators.lowbirthweight_malnutrition_preterm.value == 1) {
                medical_reason += "Low birthweight/Severe malnutrition/Preterm <br>";
            }
            if (indicators.neonate_pneumonia_ari && indicators.neonate_pneumonia_ari.value == 1) {
                medical_reason += "Pneumonia/ari <br>";
            }
            if (indicators.neonate_tetanus && indicators.neonate_tetanus.value == 1) {
                medical_reason += "Tetanus <br>";
            }
            if(medical_reason.length < 1 ) {
                medical_reason += "Unknown";
            }
        }

        if (isVerbalAutopsyChildForm(doc)) {
            if (indicators.child_accident && indicators.child_accident.value == 1) {
                medical_reason += "Child Accident <br>";
            }
            if (indicators.child_diarrhea_dysentery_any && indicators.child_diarrhea_dysentery_any.value == 1) {
                medical_reason += "Any Diarrhea/Dysentry <br>";
            }
            if (indicators.child_persistent_diarrhea_dysentery && indicators.child_persistent_diarrhea_dysentery.value == 1) {
                medical_reason += "Persistent Diarrhea_Dysentry <br>";
            }
            if (indicators.child_acute_diarrhea && indicators.child_acute_diarrhea.value == 1) {
                medical_reason += "Acute Diarrhea <br>";
            }
            if (indicators.child_acute_dysentery && indicators.child_acute_dysentery.value == 1) {
                medical_reason += "Acute Dysentry <br>";
            }
            if (indicators.child_malaria && indicators.child_malaria.value == 1) {
                medical_reason += "Malaria <br>";
            }
            if (indicators.child_malnutrition && indicators.child_malnutrition.value == 1) {
                medical_reason += "Malnutrition <br>";
            }
            if (indicators.child_measles && indicators.child_measles.value == 1) {
                medical_reason += "Measles <br>";
            }
            if (indicators.child_meningitis && indicators.child_meningitis.value == 1) {
                medical_reason += "Meningitis <br>";
            }
            if (indicators.child_pneumonia_ari && indicators.child_pneumonia_ari.value == 1) {
                medical_reason += "Pneumonia/ari <br>";
            }
            if(medical_reason.length < 1 ) {
                medical_reason += "Unknown";
            }
        }

        if (isVerbalAutopsyAdultForm(doc)) {
            if (indicators.adult_abortion && indicators.adult_abortion.value == 1) {
                medical_reason += "Abortion <br>";
            }
            if (indicators.adult_accident && indicators.adult_accident.value == 1) {
                medical_reason += "Accident <br>";
            }
            if (indicators.antepartum_haemorrhage && indicators.antepartum_haemorrhage.value == 1) {
                medical_reason += "Antepartum_Haemorrhage <br>";
            }
            if (indicators.postpartum_haemorrhage && indicators.postpartum_haemorrhage.value == 1) {
                medical_reason += "Postpartum Haemorrhage <br>";
            }
            if (indicators.adult_eclampsia && indicators.adult_eclampsia.value == 1) {
                medical_reason += "Eclampsia <br>";
            }
            if (indicators.obstructed_labour && indicators.obstructed_labour.value == 1) {
                medical_reason += "Obstructed Labour <br>";
            }
            if (indicators.adult_pleural_sepsis && indicators.adult_pleural_sepsis.value == 1) {
                medical_reason += "Peural Sepsis <br>";
            }
            if(medical_reason.length < 1 ) {
                medical_reason += "Unknown";
            }
        }

        indicator_keys["medical_reason"] =  medical_reason;

        emit([close_date.getUTCMonth(), close_date.getUTCFullYear()], indicator_keys);
    }
}