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

            if (edd_date >= visit_date && difference <= 150*MS_IN_DAY) {
                indicator_emits["anc_visit_120"] = case_id;
                if (indicators.cur_num_anc) {
                    try {
                        var cur_anc = (indicators.cur_num_anc.value) ? parseInt(indicators.cur_num_anc.value) : 0;
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

            if (edd_date >= visit_date && difference <= one_month_ms && indicators.cur_num_anc) {
                // EDD is happening within one month of this form's visit date.
                indicator_emits["visit"] = case_id;
                var cur_num_anc = (indicators.cur_num_anc.value) ? parseInt(indicators.cur_num_anc.value) : 0;
                if (cur_num_anc > 3) {
                    indicator_emits["anc4"] = case_id;
                }
            }
        }

        if ((indicators.muac_m && indicators.muac_m.value) || 
            (indicators.update_muac && indicators.update_muac.value &&
            ((indicators.muac && indicators.muac.value) ||
            (indicators.smuac && indicators.smuac.value)))) {
                var muac = parseFloat(indicators.muac.value),
                    smuac = parseFloat(indicators.smuac.value),
                    muac_m = parseFloat(indicators.muac_m.value),
                    update_muac = indicators.update_muac.value;
                if (muac !=="" || (update_muac == "yes" && (muac !=="" || smuac !==""))) {
                    indicator_emits["muac"] = case_id;

                    if ((muac || muac_m) < 210 || smuac < 21){
                        indicator_emits["moderate_muac"] = case_id;
                    }
                }
        }

        emit_special(doc, visit_date, indicator_emits, []);
    }
}
