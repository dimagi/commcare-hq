function(doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            case_id = get_case_id(doc);

        var visit_date = new Date(meta.timeEnd);

        var indicator_entries = {};

        if (indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 1?
            var age_in_years = get_age_from_dob(indicators.child_dob.value, visit_date);
            if (age_in_years < 1) {
                indicator_entries['under1'] = case_id;
                var age_in_days = age_in_years*365;
                if (age_in_days < 180) {
                    indicator_entries['under6months'] = case_id;
                    if (indicators.exclusive_breastfeeding
                        && indicators.exclusive_breastfeeding.value === 'yes') {
                        indicator_entries['under6months_exclusive_breastfeeding'] = case_id;
                    }
                }
            }
        }

        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}