function(doc) {
    // !code util/mvp.js
    if (isChildVisitForm(doc) || isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            indicator_keys = new Array(),
            is_emergency = false,
            medicated = false;

        if (indicators.referral_type && indicators.referral_type.value) {
            // referral_type indicator is present
            is_emergency = (contained_in_indicator_value(indicators.referral_type, "emergency")
                || contained_in_indicator_value(indicators.referral_type, "basic")
                || contained_in_indicator_value(indicators.referral_type, "immediate"));

        }

        if (isChildVisitForm(doc)) {
            var has_fever_meds = (contained_in_indicator_value(indicators.fever_medication, "anti_malarial") ||
                contained_in_indicator_value(indicators.fever_medication, "coartem"));
            var has_diahrrea_meds = (contained_in_indicator_value(indicators.diarrhea_medication, "ors") ||
                contained_in_indicator_value(indicators.diarrhea_medication, "zinc"));
            medicated = has_fever_meds || has_diahrrea_meds;
        }

        if (is_emergency || medicated) {
            indicator_keys.push("urgent_referral");
        }

        if (medicated) {
            indicator_keys.push("urgent_treatment_referral");
        }

        var visit_date = new Date(meta.timeEnd);
        emit_standard(doc, visit_date, indicator_keys, [doc._id]);
    }
}
