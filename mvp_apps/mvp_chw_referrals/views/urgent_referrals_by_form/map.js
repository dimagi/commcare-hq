function(doc) {
    // !code util/mvp.js
    if (isChildVisitForm(doc) || isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            indicator_keys = new Array();

        if (indicators.referral_type && indicators.referral_type.value) {
            var is_emergency = contained_in_indicator_value(indicators.referral_type, "emergency");
            if (is_emergency) {
                indicator_keys.push("urgent_referral");
            }
            var medicated = false;
            if (isChildVisitForm(doc)) {
                var has_fever_meds = (contained_in_indicator_value(indicators.fever_medication, "anti_malarial") ||
                                        contained_in_indicator_value(indicators.fever_medication, "coartem"));
                var has_diahrrea_meds = (contained_in_indicator_value(indicators.diarrhea_medication, "ors") ||
                                        contained_in_indicator_value(indicators.diarrhea_medication, "zinc"));
                medicated = has_fever_meds || has_diahrrea_meds;
            }
            if (medicated || is_emergency) {
                indicator_keys.push("urgent_treatment_referral");
            }
        }
        var visit_date = new Date(meta.timeEnd);
        emit_standard(doc, visit_date, indicator_keys, [doc._id]);
    }
}
