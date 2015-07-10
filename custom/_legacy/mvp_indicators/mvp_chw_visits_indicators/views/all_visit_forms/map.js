function(doc) {
    // !code util/mvp.js
    if( isChildVisitForm(doc) ||
        isPregnancyVisitForm(doc) ||
        isChildWelfareForm(doc) ||
        isHomeVisitForm(doc)) {

        function get_pregnancy_start_from_edd_date(edd_date) {
            var preg_start = new Date(),
                gestation_ms = 266*MS_IN_DAY;
            var start_ms = edd_date.getTime() - gestation_ms;
            preg_start.setTime(start_ms);
            return preg_start;
        }

        function get_danger_signs(danger_sign_value) {
            var signs = danger_sign_value.trim().toLowerCase();
            if (signs) {
                signs = signs.split(' ');
                return signs;
            }
            return [];
        }

        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            case_id = get_case_id(doc),
            emergency_signs = [];

        var visit_date = new Date(meta.timeEnd);

        var indicator_entries = {};

        try {
            emergency_signs = get_danger_signs(indicators.emergency_danger_sign.value);
        } catch (err) {
            // pass
        }

        if (isChildWelfareForm(doc) && indicators.vaccination_status && indicators.vaccination_status.value === 'yes') {
            // special case for Bonsaaso
            indicator_entries['child under1 not_immunized'] = case_id;
        }

        if ((isChildVisitForm(doc) || isChildWelfareForm(doc)) && indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 5?
            var age = get_age_from_dob(indicators.child_dob.value, visit_date);
            var not_immunized = false;
            if (age < 1825*MS_IN_DAY) {
                if (age < 365*MS_IN_DAY) {
                    if (indicators.vaccination_status && indicators.vaccination_status.value) {
                        var is_immunized = (indicators.vaccination_status.value === 'yes');
                        if (is_immunized && indicators.vaccination_status_6weeks) {
                            // start looking at timelines for vaccinations too.
                            if (age > 75 * MS_IN_DAY) {
                                // at least 6 weeks old
                                is_immunized = is_immunized && (indicators.vaccination_status_6weeks.value === 'yes');
                            }
                            if (age > 105 * MS_IN_DAY && indicators.vaccination_status_10weeks) {
                                is_immunized = is_immunized && (indicators.vaccination_status_10weeks.value === 'yes');
                            }
                            if (age > 135 * MS_IN_DAY && indicators.vaccination_status_14weeks) {
                                is_immunized = is_immunized && (indicators.vaccination_status_14weeks.value === 'yes');
                            }
                            if (age > 300 * MS_IN_DAY && indicators.vaccination_status_36weeks) {
                                is_immunized = is_immunized && (indicators.vaccination_status_36weeks.value === 'yes');
                            }
                        }

                        if (!is_immunized) {
                            indicator_entries['child under1 not_immunized'] = case_id;
                        }
                    }

                    if (age > 45 * MS_IN_DAY){
                        if (indicators.vaccination_birth && indicators.vaccination_birth.value === 'no') {
                            not_immunized = true;
                        }
                        //OPV0
                        if (indicators.vaccination_birth_2 && indicators.vaccination_birth_2.value === 'no') {
                            not_immunized = true;
                        }
                    }
                    if (age > 75 * MS_IN_DAY) {
                        if (indicators.vaccination_6week && indicators.vaccination_6week.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_penta1 && indicators.vaccination_penta1.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_pneumococi1 && indicators.vaccination_pneumococi1.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_rotavirus1 && indicators.vaccination_rotavirus1.value === 'no') {
                            not_immunized = true;
                        }
                    }
                    if (age > 105 * MS_IN_DAY) {
                        if (indicators.vaccination_10week && indicators.vaccination_10week.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_penta2 && indicators.vaccination_penta2.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_pneumococi2 && indicators.vaccination_pneumococi2.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_rotavirus2 && indicators.vaccination_rotavirus2.value === 'no') {
                            not_immunized = true;
                        }
                    }
                    if (age > 135 * MS_IN_DAY) {
                        if (indicators.vaccination_14week && indicators.vaccination_14week.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_penta3 && indicators.vaccination_penta3.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_pneumococi3 && indicators.vaccination_pneumococi3.value === 'no') {
                            not_immunized = true;
                        }
                    }
                    if (age > 300 * MS_IN_DAY) {
                        if (indicators.vaccination_36week && indicators.vaccination_36week.value === 'no') {
                            not_immunized = true;
                        }
                        if (indicators.vaccination_yellow_fever && indicators.vaccination_yellow_fever.value === 'no') {
                            not_immunized = true;
                        }
                    }

                    if (not_immunized) {
                        indicator_entries['child under1 not_immunized'] = case_id;
                    }
                    if (isChildWelfareForm(doc)) {
                        indicator_entries['child under1_welfare'] = case_id;
                    }
                    if (isChildVisitForm(doc)) {
                        indicator_entries['child under1'] = case_id;
                        if (age < 180*MS_IN_DAY) {
                            indicator_entries['child under6mo'] = case_id;
                            if (indicators.exclusive_breastfeeding
                                && indicators.exclusive_breastfeeding.value === 'yes') {
                                indicator_entries['child under6mo_ex_breast'] = case_id;
                            }
                        }
                        if (age < 29*MS_IN_DAY) {
                            // This under5 child is also neonate
                            indicator_entries["child neonate"] = case_id;
                        }
                        if (age < 8*MS_IN_DAY) {
                            indicator_entries["child 7days"] = case_id;
                        }
                    }
                }
                if (isChildVisitForm(doc)) {
                    indicator_entries['child under5'] = case_id;
                }
            }
        }

        if (isPregnancyVisitForm(doc)) {
            indicator_entries['pregnancy'] = case_id;

            if (indicators.pregnancy_edd && indicators.pregnancy_edd.value
                && indicators.pregnancy_end) {
                var is_currently_pregnant = true,
                    edd_date = new Date(indicators.pregnancy_edd.value);
                var start_date = get_pregnancy_start_from_edd_date(edd_date);
                if (start_date > visit_date) {
                    // Strange. Shouldn't happen. But Pregnancy of related case happened before this visit.
                    is_currently_pregnant = false;
                }
                if (is_currently_pregnant && indicators.pregnancy_end.value) {
                    var end_date = new Date(indicators.pregnancy_end.value);
                    if (end_date <= visit_date) {
                        // pregnancy has ended.
                        is_currently_pregnant = false;
                    }
                }
                if (is_currently_pregnant) {
                    indicator_entries["currently_pregnant"] = case_id;
                }
            }
        }

        if (isHomeVisitForm(doc)) {
            indicator_entries['household'] = case_id;
            if (indicators.num_bednets_observed && indicators.num_bednets_observed.value &&
                indicators.num_sleeping_site && indicators.num_sleeping_site.value) {
                indicator_entries['household bednet'] = case_id;
                if (indicators.num_bednets_observed.value >= indicators.num_sleeping_site.value) {
                    indicator_entries['household atleastonebednet'] = case_id;
                }
            }
            if (indicators.handwashing && indicators.handwashing.value) {
                indicator_entries['household handwashing'] = case_id;
                var handwashing_area = indicators.handwashing.value;
                if (handwashing_area.indexOf("latrine") >= 0) {
                    indicator_entries['household handwashing10metres'] = case_id;
                }
            }
        }

        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}
