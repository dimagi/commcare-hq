function (doc) {
    // !code util/mvp.js
    if (isChildRegistrationForm(doc) ||
        isPregnancyCloseForm(doc)) {
        var meta = doc.form.meta,
            indicators = get_indicators(doc),
            indicator_keys = [];

        var birth_weight = null,
            birth_weight_nan = false,
            reg_date;

        if (doc.dob || doc.dob_calc) {
            var dob_date = doc.dob_calc || doc.dob;
            reg_date = new Date(dob_date);
        } else {
            reg_date = new Date(meta.timeEnd);
        }

        try {
            birth_weight = (indicators.weight_at_birth && indicators.weight_at_birth.value) ? parseFloat(indicators.weight_at_birth.value) : 0;
        } catch (e) {
            birth_weight_nan = true;
        }


        indicator_keys.push("registration");
        if (indicators.delivered_in_facility
            && indicators.delivered_in_facility.value === 'yes') {
            indicator_keys.push("facility_delivery");
        }
        if (birth_weight >= 0 && !birth_weight_nan) {
            indicator_keys.push("birth_weight");
            if (birth_weight < 2.5) {
                indicator_keys.push("birth_weight low");
            }
        }

        emit_standard(doc, reg_date, indicator_keys, []);
    }
}
