function (doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc);

        if (indicators.child_dob && indicators.child_dob.value) {
            var meta = doc.form.meta,
                indicator_entries = {},
                age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd),
                visit_date = new Date(meta.timeEnd),
                case_id = get_case_id(doc);

            if (age >= 180*MS_IN_DAY && age < 1770*MS_IN_DAY && indicators.muac.value) {
                // MUAC reading taken during visit
                indicator_entries["muac_reading"] = 1;
                try {
                    var muac_value = parseFloat(indicators.muac.value);
                    if (muac_value < 125.0) {
                        indicator_entries["muac_wasting"] = 1;
                    }
                } catch (err) {
                    log("MUAC value could not be obtained");
                }

                if (doc.form.last_muac) {
                    var last_muac = new Date(doc.form.last_muac);
                    if (last_muac <= visit_date) {
                        var difference = visit_date.getTime() - last_muac.getTime();
                        if (difference <= 90*MS_IN_DAY){
                            indicator_entries["routine_muac"] = case_id;
                        }
                    }
                }
            }
            emit_special(doc, visit_date, indicator_entries, [doc._id]);
        }

    }
}
