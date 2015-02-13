function(doc) {
    // !code util/mvp.js
    // !code util/danger_signs.js
    if(isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            visit_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = [],
            immediate_signs = [],
            emergency_signs = [];

        try {
            immediate_signs = get_danger_signs(indicators.immediate_danger_sign.value);
        } catch (err) {
            // pass
        }

        try {
            emergency_signs = get_danger_signs(indicators.emergency_danger_sign.value);
        } catch (err) {
            // pass
        }

        if (immediate_signs.length > 0 || emergency_signs.length > 0) {
            indicator_keys.push("danger_sign");
            if (indicators.referral_type && indicators.referral_type.value &&
                indicators.referral_type.value !== 'none' && indicators.referral_type.value !== 'convenient') {
                indicator_keys.push("danger_sign referred");
            }
        }

        emit_standard(doc, visit_date, indicator_keys, []);
    }
}
