function (doc) {
    // !code util/mvp.js
    if (isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            case_id = get_case_id(doc);

        var visit_date = new Date(meta.timeEnd),
            indicator_emits = {};

        if (indicators.pregnancy_edd && indicators.pregnancy_edd.value) {
            var edd = indicators.pregnancy_edd.value,
                one_month_ms = 30*MS_IN_DAY,
                gestation_ms = 40*7*MS_IN_DAY;

            var edd_date = new Date(edd);
            var difference = edd_date.getTime() - visit_date.getTime();

            if (edd_date >= visit_date && difference <= 120*MS_IN_DAY) {
                indicator_emits["anc_visit_120"] = case_id;
                if (indicators.cur_num_anc) {
                    try {
                        var cur_anc = (indicators.cur_num_anc.value) ? parseInt(indicators) : 0;
                        if (cur_anc === 0) {
                            indicator_emits["no_anc"] = case_id;
                        }
                    } catch (e) {
                        if (indicators.cur_num_anc.value === "" || indicators.cur_num_anc.value === "no") {
                            // handle sauri case
                            indicator_emits["no_anc"] = case_id;
                        }
                    }
                }
            }

            if (edd_date >= visit_date && difference <= one_month_ms &&
                indicators.num_anc && indicators.prev_num_anc &&
                (indicators.last_anc_date || indicators.last_anc_weeks)) {
                var num_ancs = (indicators.num_anc.value) ? parseInt(indicators.num_anc.value) : 0,
                    prev_num_ancs = (indicators.prev_num_anc.value) ? parseInt(indicators.prev_num_anc.value) : 0;

                // EDD is happening within one month of this form's visit date.
                indicator_emits["visit"] = case_id;
                var count_anc = false;

                if (indicators.last_anc_weeks && indicators.last_anc_weeks.value) {
                    // dealing with weeks ago
                    var anc_weeks = parseInt(indicators.last_anc_weeks.value);
                    if (anc_weeks <= 40) {
                        // weeks within time frame
                        count_anc = true;
                    }
                } else if(indicators.last_anc_date && indicators.last_anc_date.value) {
                    var last_anc_date = new Date(indicators.last_anc_date.value);
                    var anc_difference = edd_date.getTime() - last_anc_date.getTime();
                    if (edd_date > last_anc_date
                        && anc_difference <= gestation_ms
                        && anc_difference >= one_month_ms) {
                        count_anc = true;
                    }
                }
                var anc_total = prev_num_ancs;
                if (count_anc) {
                    anc_total += num_ancs;
                }
                if (anc_total > 3) {
                    indicator_emits["anc4"] = case_id;
                }
            }
        }

        emit_special(doc, visit_date, indicator_emits, []);
    }
}
