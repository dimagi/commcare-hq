function(doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta;
        var indicator_keys = new Array();
        if (indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 1?
            var age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd);
            if (age < 1) {
                indicator_keys.push('under1');
                var age_in_months = age*12;
                if (age_in_months < 6) {
                    indicator_keys.push('under6months');
                    if (indicators.exclusive_breastfeeding
                        && indicators.exclusive_breastfeeding.value === 'yes') {
                        indicator_keys.push('under6months exclusive_breastfeeding');
                    }
                }
            }
        }
    }
}