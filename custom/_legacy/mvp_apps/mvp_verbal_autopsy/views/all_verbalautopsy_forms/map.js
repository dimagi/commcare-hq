function (doc) {
    // !code util/mvp.js
    if (isVerbalAutopsyNeonateForm(doc) ||
        isVerbalAutopsyChildForm(doc) ||
        isVerbalAutopsyAdultForm(doc)) {

        var indicators = get_indicators(doc),
            closed_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = [],
            death_place,
            report_date;

        if (indicators.date_of_,death && indicators.date_of_death.value) {
            report_date = new Date(indicators.date_of_death.value);
        } else {
            report_date = closed_date;
        }

        if (isVerbalAutopsyNeonateForm(doc)) {
            indicator_keys.push("va_neonate");
            indicator_keys.push("va_0to59");
            //deathplace
            if (indicators.death_place && indicators.death_place) {
                death_place = indicators.death_place.value;
                if (death_place == 11) {
                    indicator_keys.push("death_hosp");
                }
                if (death_place == 12) {
                    indicator_keys.push("death_facility");
                }
                if (death_place == 14) {
                    indicator_keys.push("death_home");
                }
                if (death_place == 13) {
                    indicator_keys.push("death_route");
                }
            }

            if (indicators.birth_asphyxia && indicators.birth_asphyxia.value == 1) {
                indicator_keys.push("va_birth_asphyxia");
            }
            else if (indicators.birth_trauma && indicators.birth_trauma.value == 1) {
                indicator_keys.push("va_birth_trauma");
            }
            else if (indicators.congenital_abnormality && indicators.congenital_abnormality.value == 1) {
                indicator_keys.push("va_congenital_abnormality");
            }
            else if (indicators.neonate_diarrhea_dysentery && indicators.neonate_diarrhea_dysentery.value == 1) {
                indicator_keys.push("va_neonate_diarrhea_dysentery");
            }
            else if (indicators.lowbirthweight_malnutrition_preterm && indicators.lowbirthweight_malnutrition_preterm.value == 1) {
                indicator_keys.push("va_lowbirthweight_malnutrition_preterm");
            }
            else if (indicators.neonate_pneumonia_ari && indicators.neonate_pneumonia_ari.value == 1) {
                indicator_keys.push("va_neonate_pneumonia_ari");
            }
            else if (indicators.neonate_tetanus && indicators.neonate_tetanus.value == 1) {
                indicator_keys.push("va_neonate_tetanus");
            }
            else {
                indicator_keys.push("va_neonate_unknown");
            }
        }

        if (isVerbalAutopsyChildForm(doc)) {
            indicator_keys.push("va_child");
            indicator_keys.push("va_0to59");
            //deathplace
            if (indicators.death_place && indicators.death_place) {
                death_place = indicators.death_place.value;
                if (death_place == 11) {
                    indicator_keys.push("death_hosp");
                }
                if (death_place == 12) {
                    indicator_keys.push("death_facility");
                }
                if (death_place == 14) {
                    indicator_keys.push("death_home");
                }
                if (death_place == 13) {
                    indicator_keys.push("death_route");
                }
            }

            if (indicators.child_accident && indicators.child_accident.value == 1) {
                indicator_keys.push("va_child_accident");
            }
            else if (indicators.child_diarrhea_dysentery_any && indicators.child_diarrhea_dysentery_any.value == 1) {
                indicator_keys.push("va_child_diarrhea_dysentery_any");
            }
            else if (indicators.child_persistent_diarrhea_dysentery && indicators.child_persistent_diarrhea_dysentery.value == 1) {
                indicator_keys.push("va_child_persistent_diarrhea_dysentery");
            }
            else if (indicators.child_acute_diarrhea && indicators.child_acute_diarrhea.value == 1) {
                indicator_keys.push("va_child_acute_diarrhea");
            }
            else if (indicators.child_acute_dysentery && indicators.child_acute_dysentery.value == 1) {
                indicator_keys.push("va_child_acute_dysentery");
            }
            else if (indicators.child_malaria && indicators.child_malaria.value == 1) {
                indicator_keys.push("va_child_malaria");
            }
            else if (indicators.child_malnutrition && indicators.child_malnutrition.value == 1) {
                indicator_keys.push("va_child_malnutrition");
            }
            else if (indicators.child_measles && indicators.child_measles.value == 1) {
                indicator_keys.push("va_child_measles");
            }
            else if (indicators.child_meningitis && indicators.child_meningitis.value == 1) {
                indicator_keys.push("va_child_meningitis");
            }
            else if (indicators.child_pneumonia_ari && indicators.child_pneumonia_ari.value == 1) {
                indicator_keys.push("va_child_pneumonia_ari");
            }
            else {
                indicator_keys.push("va_child_unknown");
            }
        }

        if (isVerbalAutopsyAdultForm(doc)) {
            indicator_keys.push("va_adult_maternal");
            if (indicators.adult_abortion && indicators.adult_abortion.value == 1) {
                indicator_keys.push("va_adult_abortion");
            }
            else if (indicators.adult_accident && indicators.adult_accident.value == 1) {
                indicator_keys.push("va_adult_accident");
            }
            else if (indicators.antepartum_haemorrhage && indicators.antepartum_haemorrhage.value == 1) {
                indicator_keys.push("va_adult_antepartum_haemorrhage");
            }
            else if (indicators.postpartum_haemorrhage && indicators.postpartum_haemorrhage.value == 1) {
                indicator_keys.push("va_adult_postpartum_haemorrhage");
            }
            else if (indicators.adult_eclampsia && indicators.adult_eclampsia.value == 1) {
                indicator_keys.push("va_adult_eclampsia");
            }
            else if (indicators.obstructed_labour && indicators.obstructed_labour.value == 1) {
                indicator_keys.push("va_adult_obstructed_labour");
            }
            else if (indicators.adult_pleural_sepsis && indicators.adult_pleural_sepsis.value == 1) {
                indicator_keys.push("va_adult_pleural_sepsis");
            }
            else {
                indicator_keys.push("va_child_unknown");
            }
        }

        emit_standard(doc, report_date, indicator_keys, []);
    }
}
