function(doc) {
    // !code util/mvp.js
    if( isChildVisitForm(doc) ||
        isPregnancyVisitForm(doc) ||
        isHomeVisitForm(doc)) {

        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            case_id = get_case_id(doc);

        var visit_date = new Date(meta.timeEnd);

        var indicator_entries = {};

        if (isChildVisitForm(doc) && indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 5?
            var age_in_years = get_age_from_dob(indicators.child_dob.value, visit_date);
            if (age_in_years < 5) {
                indicator_entries['child under5'] = case_id;
                if (age_in_years < 1) {
                    indicator_entries['child under1'] = case_id;

                    var age_in_days = age_in_years*365;
                    if (age_in_days < 180) {
                        indicator_entries['child under6mo'] = case_id;
                        if (indicators.exclusive_breastfeeding
                            && indicators.exclusive_breastfeeding.value === 'yes') {
                            indicator_entries['child under6mo_ex_breast'] = case_id;
                        }
                    }
                    if (age_in_days < 31) {
                        // This under5 child is also neonate
                        indicator_entries["child neonate"] = case_id;
                    }
                    if (age_in_days <= 7) {
                        indicator_entries["child 7days"] = case_id;
                    }
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
        }

        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}
