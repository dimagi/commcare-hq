function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) || isPregnancyCase(doc)) {
        var indicators = get_indicators(doc),
            emergency_medication = false;

        if (isChildCase(doc) && (indicators.fever_medication || indicators.diarrhea_medication))

            if (indicators.referral_type && indicators.referral_type.value) {
                var referrals = indicators.referral_type.value,
                    visit_dates = [],
                    urgent_dates = [];

                var fever_medications = {},
                    diarrhea_medications = {};

                if (isChildCase(doc)) {
                    if (indicators.fever_medication && indicators.fever_medication.value) {
                        fever_medications = indicators.fever_medication.value;
                    }
                    if (indicators.diarrhea_medication && indicators.diarrhea_medication.value) {
                        diarrhea_medications = indicators.diarrhea_medication.value;
                    }
                }

                for (var r in referrals) {
                    if (referrals.hasOwnProperty(r)) {
                        var referral_doc = referrals[r];

                        var is_medicated_child = false;
                        if(isChildCase(doc)) {
                            try {
                                is_medicated_child =  (contained_in_indicator_value(fever_medications[r], "coartem") ||
                                    contained_in_indicator_value(fever_medications[r], "anti_malarial") ||
                                    contained_in_indicator_value(diarrhea_medications[r],"ors"));
                            } catch (e) {
                                // do nothing
                            }
                        }

                        if (contained_in_indicator_value(referral_doc, "emergency") &&
                            (isPregnancyCase(doc) || is_medicated_child)) {
                            // This is an urgent referral
                            urgent_dates.push(new Date(referral_doc.timeEnd));
                        } else {
                            visit_dates.push(new Date(referral_doc.timeEnd));
                        }
                    }
                }

                for (var u = 0; u < urgent_dates.length; u++) {
                    for (var v = 0; v < visit_dates.length; v++) {
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
