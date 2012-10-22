function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) || isPregnancyCase(doc)) {
        var indicators = get_indicators(doc),
            two_days_ms = 2*MS_IN_DAY,
            user_id = get_user_id(doc);
        if (indicators.referral_type) {
            var referrals = indicators.referral_type.value,
                visit_dates = new Array(),
                urgent_dates = new Array();
            for (var r in referrals) {
                var referral_doc = referrals[r];
                if (referral_doc.value && referral_doc.value.toLowerCase().indexOf("emergency") >= 0) {
                    // This is an urgent referral
                    urgent_dates.push(new Date(referral_doc.timeEnd));
                } else {
                    visit_dates.push(new Date(referral_doc.timeEnd));
                }
            }
            for (var u in urgent_dates) {
                for (var v in visit_dates) {
                    var urgent_visit = urgent_dates[u],
                        reg_visit = visit_dates[v];
                    if (reg_visit > urgent_visit) {
                        var difference = reg_visit.getTime() - urgent_visit.getTime();
                        if (difference <= two_days_ms) {
                            emit(smart_date_emit_key(["all", doc.domain, "urgent_referral_followup"], urgent_visit, [doc._id]), 1);
                            emit(smart_date_emit_key(["user", doc.domain, user_id, "urgent_referral_followup"], urgent_visit, [doc._id]), 1);
                        }
                    }
                }
            }
        }
    }
}