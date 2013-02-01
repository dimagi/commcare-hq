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

            if (age >= 180*MS_IN_DAY && age < 1770*MS_IN_DAY) {
                if (indicators.cur_muac && indicators.cur_muac.value) {
                    try {
                        var cur_muac = parseFloat(indicators.cur_muac.value);
                        last_muac_indicators["muac_reading"] = case_id;
                        if (cur_muac < 125.0) {
                            last_muac_indicators["muac_wasting"] = case_id;
                        }
                    } catch (e) {
                        // do nothing
                    }
                }
                if (visit_date >= last_muac_date
                    && indicators.muac && indicators.muac.value) {
                    var visit_diff = visit_date.getTime() - last_muac_date.getTime();
                    if (visit_diff < 90*MS_IN_DAY) {
                        visit_indicators["routine_muac"] = case_id;
                    }
                }
            }

            emit_special(doc, last_muac_date, last_muac_indicators, [doc._id]);
            emit_special(doc, visit_date, visit_indicators, [doc._id]);
        }
    }
}
