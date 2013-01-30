function (doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc);

        if (indicators.child_dob && indicators.child_dob.value &&
            indicators.last_muac && indicators.last_muac.value) {
            var meta = doc.form.meta,
                indicator_entries = {},
                age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd),
                last_muac_date = new Date(indicators.last_muac.value),
                case_id = get_case_id(doc);

            if (age > 180*MS_IN_DAY && age < 1770*MS_IN_DAY) {
                if (indicators.cur_muac && indicators.cur_muac.value) {
                    try {
                        var cur_muac = parseFloat(indicators.cur_muac.value);
                        indicator_entries["muac_reading"] = case_id;
                        if (cur_muac < 125.0) {
                            indicator_entries["muac_wasting"] = case_id;
                        }
                    } catch (e) {
                        // do nothing
                    }
                }
                indicator_entries["routine_muac"] = case_id;
            }
            emit_special(doc, last_muac_date, indicator_entries, [doc._id]);
        }

    }
}
