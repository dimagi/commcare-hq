function (doc) {
    // !code util/mvp.js
    if (isChildRegistrationForm(doc)) {
        var meta = doc.form.meta,
            indicators = get_indicators(doc),
            indicator_keys = new Array();

        var reg_date = new Date(meta.timeEnd),
            birth_weight = null;

        try {
            birth_weight = (indicators.weight_at_birth && indicators.weight_at_birth.value) ? parseInt(indicators.weight_at_birth.value) : 0;
        } catch (e) {
            // do nothing
        }


        indicator_keys.push("registration");
        if (indicators.delivered_in_facility
            && indicators.delivered_in_facility.value === 'yes') {
            indicator_keys.push("facility_delivery");
        }
        if (birth_weight > 0) {
            indicator_keys.push("birth_weight");
            if (birth_weight < 2.5) {
                indicator_keys.push("birth_weight low");
            }
        }

        emit_standard(doc, reg_date, indicator_keys, []);
    }
}
