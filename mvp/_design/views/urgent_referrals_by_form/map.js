function(doc) {
    // !code util/mvp.js
    if (isChildVisitForm(doc) || isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            indicator_keys = new Array();

        if (indicators.referral_type) {
            var referral_type = indicators.referral_type.value;
            if (referral_type && referral_type.toLowerCase().indexOf("emergency") >= 0) {
                indicator_keys.push("urgent_referral");
            }
        }
        var visit_date = new Date(meta.timeEnd);
        emit_standard(doc, visit_date, indicator_keys, [doc._id]);
    }
}