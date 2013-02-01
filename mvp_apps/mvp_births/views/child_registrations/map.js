function (doc) {
    // !code util/mvp.js
    if (isChildRegistrationForm(doc)) {
        var meta = doc.form.meta,
            indicators = get_indicators(doc),
            indicator_keys = new Array();

        var reg_date = new Date(meta.timeEnd),
            birth_weight = null,
            birth_weight_nan = false;

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
