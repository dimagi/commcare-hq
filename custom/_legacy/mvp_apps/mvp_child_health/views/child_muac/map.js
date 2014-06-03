function (doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc);

        if (indicators.child_dob && indicators.child_dob.value &&
            indicators.last_muac && indicators.last_muac.value) {
            var meta = doc.form.meta,
                last_muac_indicators = {},
                visit_indicators = {},
                age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd),
                last_muac_date = new Date(indicators.last_muac.value),
                visit_date = new Date(meta.timeEnd),
                case_id = get_case_id(doc);

            if (visit_date >= last_muac_date) {
                var visit_diff = visit_date.getTime() - last_muac_date.getTime();
            }

            if (age >= 180*MS_IN_DAY && age < 1825*MS_IN_DAY) {
                if (indicators.cur_muac && indicators.cur_muac.value) {
                    try {
                        var cur_muac = parseFloat(indicators.cur_muac.value);
                        last_muac_indicators["muac_reading"] = case_id;
                        if ((cur_muac < 125.0 && cur_muac > 49) || (cur_muac <12.5)) {
                            last_muac_indicators["muac_wasting"] = case_id;
                        }
                    } catch (e) {
                        // do nothing
                    }
                }
                if (indicators.muac && indicators.muac.value && visit_diff < 30*MS_IN_DAY) {
                    visit_indicators["routine_muac"] = case_id;
                }
            }

            if (age >= 180*MS_IN_DAY && age < 1825*MS_IN_DAY && indicators.cur_muac
                && indicators.cur_muac.value && visit_diff < 30*MS_IN_DAY) {
                try {
                    var cur_muac_under5 = parseFloat(indicators.cur_muac.value);
                    visit_indicators["active_gam"] = {
                        "_id": case_id,
                        "value": (cur_muac_under5 < 125.0 && cur_muac_under5 > 49.0) ? 1 : 0 || (cur_muac_under5 < 12.5) ? 1 : 0
                    }
                } catch (e) {
                    // do nothing
                }
            }

            emit_special(doc, last_muac_date, last_muac_indicators, [doc._id]);
            emit_special(doc, visit_date, visit_indicators, [doc._id]);
        }
    }
}
