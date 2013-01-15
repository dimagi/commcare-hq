function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) || isPregnancyCase(doc)) {
        var emitFollowUps = function (flagged_dates, normal_dates) {
            var self = this;
            self.flagged = flagged_dates;
            self.normal = normal_dates;

            function _compareVisitAndFlagged(flagged_date) {
                for (var n = 0; n < self.normal.length; n++) {
                    var normal_date = self.normal[n];

                    if (normal_date > flagged_date) {
                        var difference = (normal_date.getTime() - flagged_date.getTime()) / MS_IN_DAY;

                        emit_special(doc, flagged_date, {urgent_referral_followup_days: difference}, [doc._id]);
                        if (difference <= 2) {
                            emit_standard(doc, flagged_date, ["urgent_referral_followup"], [doc._id]);
                        }
                        return;
                    }
                }
            }

            for (var f = 0; f < self.flagged.length; f++) {
                var flagged_visit = self.flagged[f];
                _compareVisitAndFlagged(flagged_visit);
            }
        };

        var indicators = get_indicators(doc);

        if ((indicators.referral_type && indicators.referral_type.value)) {
            // Just looking at emergency followups

            var referrals = indicators.referral_type.value,
                visit_dates = [],
                urgent_dates = [];

            for (var r in referrals) {
                if (referrals.hasOwnProperty(r)) {
                    var referral_doc = referrals[r];
                    if (contained_in_indicator_value(referral_doc, "emergency") ||
                        contained_in_indicator_value(referral_doc, "immediate") ||
                        contained_in_indicator_value(referral_doc, "basic")) {
                        // This is an urgent referral
                        urgent_dates.push(new Date(referral_doc.timeEnd));
                    } else {
                        visit_dates.push(new Date(referral_doc.timeEnd));
                    }
                }
            }

            emitFollowUps(urgent_dates, visit_dates);
        }

        if (isChildCase(doc) && (indicators.fever_medication && indicators.diarrhea_medication)) {
            var fever_medications = {},
                diarrhea_medications = {},
                other_visit_dates = [],
                treatment_dates = [];

            if (indicators.fever_medication && indicators.fever_medication.value) {
                fever_medications = indicators.fever_medication.value;
            }
            if (indicators.diarrhea_medication && indicators.diarrhea_medication.value) {
                diarrhea_medications = indicators.diarrhea_medication.value;
            }
            var has_dmed = false,
                has_fmed = false;

            for (var m in fever_medications) {
                if (fever_medications.hasOwnProperty(m)) {
                    var fever_med_doc = fever_medications[m],
                        diarrhea_med_doc = diarrhea_medications[m];

                    has_fmed = (contained_in_indicator_value(fever_med_doc, "coartem") ||
                                contained_in_indicator_value(fever_med_doc, "anti_malarial"));
                    has_dmed = (contained_in_indicator_value(diarrhea_med_doc,"ors") ||
                                contained_in_indicator_value(diarrhea_med_doc,"zinc"));

                    if (has_dmed || has_fmed) {
                        treatment_dates.push(new Date(fever_med_doc.timeEnd));
                    } else {
                        other_visit_dates.push(new Date(fever_med_doc.timeEnd));
                    }
                }
            }

            emitFollowUps(treatment_dates, other_visit_dates);
        }

    }
}
