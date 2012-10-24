function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) || isPregnancyCase(doc)) {
        var indicators = get_indicators(doc);

        if (indicators.referral_type && indicators.referral_type.value) {
            var referrals = indicators.referral_type.value,
                visit_dates = new Array(),
                urgent_dates = new Array();

            for (var r in referrals) {
                var referral_doc = referrals[r];
                if (contained_in_indicator_value(indicators.referral_type, "emergency")) {
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
                        var difference = (reg_visit.getTime() - urgent_visit.getTime())/MS_IN_DAY;
                        emit_special(doc, urgent_visit, {urgent_referral_followup_days: difference}, [doc._id]);
                        if (difference <= 2) {
                            emit_standard(doc, urgent_visit, ["urgent_referral_followup"], [doc._id]);
                        }
                    }
                }
            }
        }
    }
}