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

        report_date = closed_date;

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
            if (indicators.birth_trauma && indicators.birth_trauma.value == 1) {
                indicator_keys.push("va_birth_trauma");
            }
            if (indicators.congenital_abnormality && indicators.congenital_abnormality.value == 1) {
                indicator_keys.push("va_congenital_abnormality");
            }
            if (indicators.neonate_diarrhea_dysentery && indicators.neonate_diarrhea_dysentery.value == 1) {
                indicator_keys.push("va_neonate_diarrhea_dysentery");
            }
            if (indicators.lowbirthweight_malnutrition_preterm && indicators.lowbirthweight_malnutrition_preterm.value == 1) {
                indicator_keys.push("va_lowbirthweight_malnutrition_preterm");
            }
            if (indicators.neonate_pneumonia_ari && indicators.neonate_pneumonia_ari.value == 1) {
                indicator_keys.push("va_neonate_pneumonia_ari");
            }
            if (indicators.neonate_tetanus && indicators.neonate_tetanus.value == 1) {
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
            if (indicators.child_diarrhea_dysentery_any && indicators.child_diarrhea_dysentery_any.value == 1) {
                indicator_keys.push("va_child_diarrhea_dysentery_any");
            }
            if (indicators.child_persistent_diarrhea_dysentery && indicators.child_persistent_diarrhea_dysentery.value == 1) {
                indicator_keys.push("va_child_persistent_diarrhea_dysentery");
            }
            if (indicators.child_acute_diarrhea && indicators.child_acute_diarrhea.value == 1) {
                indicator_keys.push("va_child_acute_diarrhea");
            }
            if (indicators.child_acute_dysentery && indicators.child_acute_dysentery.value == 1) {
                indicator_keys.push("va_child_acute_dysentery");
            }
            if (indicators.child_malaria && indicators.child_malaria.value == 1) {
                indicator_keys.push("va_child_malaria");
            }
            if (indicators.child_malnutrition && indicators.child_malnutrition.value == 1) {
                indicator_keys.push("va_child_malnutrition");
            }
            if (indicators.child_measles && indicators.child_measles.value == 1) {
                indicator_keys.push("va_child_measles");
            }
            if (indicators.child_meningitis && indicators.child_meningitis.value == 1) {
                indicator_keys.push("va_child_meningitis");
            }
            if (indicators.child_pneumonia_ari && indicators.child_pneumonia_ari.value == 1) {
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
            if (indicators.adult_accident && indicators.adult_accident.value == 1) {
                indicator_keys.push("va_adult_accident");
            }
            if (indicators.antepartum_haemorrhage && indicators.antepartum_haemorrhage.value == 1) {
                indicator_keys.push("va_adult_antepartum_haemorrhage");
            }
            if (indicators.postpartum_haemorrhage && indicators.postpartum_haemorrhage.value == 1) {
                indicator_keys.push("va_adult_postpartum_haemorrhage");
            }
            if (indicators.adult_eclampsia && indicators.adult_eclampsia.value == 1) {
                indicator_keys.push("va_adult_eclampsia");
            }
            if (indicators.obstructed_labour && indicators.obstructed_labour.value == 1) {
                indicator_keys.push("va_adult_obstructed_labour");
            }
            if (indicators.adult_pleural_sepsis && indicators.adult_pleural_sepsis.value == 1) {
                indicator_keys.push("va_adult_pleural_sepsis");
            }
            else {
                indicator_keys.push("va_adult_unknown");
            }
        }

        //Social Causes of death
        if (indicators.no_formal_hc_contact && indicators.no_formal_hc_contact.value == 1) {
            indicator_keys.push("va_social_no_formal_healthcare_contact");
        }
        if (indicators.clinician_unavailable_clinic && indicators.clinician_unavailable_clinic.value == 1) {
            indicator_keys.push("va_social_clinicial_unavailable_clinic");
        }
        if (indicators.clinician_unavailable_hospital && indicators.clinician_unavailable_hospital.value == 1) {
            indicator_keys.push("va_social_clinicial_unavailable_hosp");
        }
        if (indicators.financial_barrier_hc && indicators.financial_barrier_hc.value == 1) {
            indicator_keys.push("va_social_financial_barrier");
        }
        if (indicators.barrier_med_access && indicators.barrier_med_access.value == 1) {
            indicator_keys.push("va_social_access_medication_barrier");
        }
        if (indicators.transport_access_barrier && indicators.transport_access_barrier.value == 1) {
            indicator_keys.push("va_social_access_transport_barrier");
        }
        if (indicators.comm_access_barrier && indicators.comm_access_barrier.value == 1) {
            indicator_keys.push("va_social_access_communication_barrier");
        }
        if (indicators.personal_hc_barrier && indicators.personal_hc_barrier.value == 1) {
            indicator_keys.push("va_social_personal_healthcare_barrier");
        }
        if (indicators.unmet_referral && indicators.unmet_referral.value == 1) {
            indicator_keys.push("va_social_unmet_referral");
        }
        if (indicators.delay_first_contact_mild && indicators.delay_first_contact_mild.value == 1) {
            indicator_keys.push("va_social_delay_first_contact_mild");
        }
        if (indicators.delay_first_contact_severe && indicators.delay_first_contact_severe.value == 1) {
            indicator_keys.push("va_social_delay_first_contact_severe");
        }
        if (indicators.delay_chw_to_fac_mild && indicators.delay_chw_to_fac_mild.value == 1) {
            indicator_keys.push("va_social_delay_chw_facility_mild");
        }
        if (indicators.delay_chw_to_fac_severe && indicators.delay_chw_to_fac_severe.value == 1) {
            indicator_keys.push("va_social_delay_chw_facility_severe");
        }
        if (indicators.delay_clinic_to_hos_mild && indicators.delay_clinic_to_hos_mild.value == 1) {
            indicator_keys.push("va_social_delay_clinic_hosp_mild");
        }
        if (indicators.delay_clinic_to_hos_severe && indicators.delay_clinic_to_hos_severe.value == 1) {
            indicator_keys.push("va_social_delay_clinic_hosp_severe");
        }

        emit_standard(doc, report_date, indicator_keys, []);
    }
}
