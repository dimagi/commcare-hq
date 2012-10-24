function(doc) {
    // !code util/mvp.js
    if(isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            visit_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = new Array();

        if ((indicators.immediate_danger_sign && indicators.immediate_danger_sign.value)
            || (indicators.emergency_danger_sign && indicators.emergency_danger_sign.value)) {
            indicator_keys.push("danger_sign");
            if (indicators.referral_type && indicators.referral_type.value &&
                indicators.referral_type.value !== 'none') {
                indicator_keys.push("danger_sign referred");
            }
        }

        emit_standard(doc, visit_date, indicator_keys, []);
    }
}