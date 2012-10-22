function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) && (doc.dob_calc || doc.dob)) {
        var seven_days_ms = 7*MS_IN_DAY,
            birth_date = new Date(doc.dob_calc || doc.dob),
            indicators = get_indicators(doc),
            indicator_keys = new Array();

        indicator_keys.push("dob");

        if (indicators.referral_type) {
            var visits = indicators.referral_type.value,
                seven_days_old = false;
            for (var i in visits) {
                var visit_doc = visits[i];
                var visit_end =  new Date(visit_doc.timeEnd);
                var visit_ms = visit_end.getTime() - birth_date.getTime();

                if (visit_ms <= seven_days_ms) {
                    seven_days_old = true;
                }
            }
            if (seven_days_old) {
                indicator_keys.push("newborn_visit");
            }
        }

        emit_standard(doc, birth_date, indicator_keys, [doc._id]);
    }
}