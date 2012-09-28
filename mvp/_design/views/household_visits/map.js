function(doc) {
    // !code util/mvp.js
    if(isHomeVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta;

        var case_id = doc.form['case']['@case_id'],
            child_dobs = indicators.household_child_dob.value,
            pregnancies = indicators.household_pregnancy_visit.value;

        if (meta.timeEnd && case_id) {
            emit([doc.domain, "visit", meta.timeEnd, case_id], 1);

            if (child_dobs) {
                for (var c in child_dobs) {
                    var child_dob_info = child_dobs[c];
                    if (child_dob_info.value && meta.timeEnd) {
                        var age = get_age_from_dob(child_dob_info.value, meta.timeEnd);
                        if (age) {
                            if (age < 5) {
                                // under5 indicator
                                emit([doc.domain, "under5", meta.timeEnd, case_id], 1);
                            }
                            var age_in_days = age*365;
                            if (age_in_days < 31) {
                                // neonate newborn indicator
                                emit([doc.domain, "neonate", meta.timeEnd, case_id], 1);
                            }
                        }
                    }
                }
            }

            if (pregnancies) {
                for (var p in pregnancies) {
                    var pregnancy_info = pregnancies[p];
                    var preg_start = pregnancy_info.case_opened,
                        preg_end = pregnancy_info.case_closed;
                    if (preg_start && !preg_end) {
                        var est_preg_end = new Date(preg_start);
                        est_preg_end.setTime(est_preg_end.getTime() + 42*7*MS_IN_DAY);
                        preg_end = est_preg_end.toISOString();
                    }
                    if (preg_start) {
                        var preg_start_date = new Date(preg_start),
                            preg_end_date = new Date(preg_end),
                            form_date = new Date(meta.timeEnd);
                        var is_pregnant = ((form_date >= preg_start_date) && (form_date < preg_end_date));
                        if (is_pregnant) {
                            emit([doc.domain, "pregnant", meta.timeEnd, case_id], 1);
                        }
                    }
                }
            }

        }
    }
}