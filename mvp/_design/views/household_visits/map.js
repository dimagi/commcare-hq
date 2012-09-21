function(doc) {
    if(doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B' ) {

        var definition = doc.computed_.mvp_indicators,
            meta = doc.form.meta;
        var case_id = doc.form['case']['@case_id'],
            child_dobs = definition.household_child_dob.value,
            pregnancies = definition.household_pregnancy_visit.value;
        var ms_day = 24*60*60*1000;
        var ms_year = 365*ms_day;

        if (case_id) {
            emit([doc.domain, "visit", meta.timeEnd, case_id], 1);

            if (child_dobs) {
                for (var c in child_dobs) {
                    var child_dob_info = child_dobs[c];
                    if (child_dob_info.value) {
                        var time_end_date = new Date(meta.timeEnd),
                            dob = new Date(child_dob_info.value);

                        if (time_end_date >= dob) {
                            var age = (time_end_date.getTime() - dob.getTime())/ms_year;
                            if (age < 5) {
                                // under5 indicator
                                emit([doc.domain, "visit under5", meta.timeEnd, case_id], 1);
                            }
                            var age_in_days = age*365;
                            if (age_in_days < 31) {
                                // neonate newborn indicator
                                emit([doc.domain, "visit neonate", meta.timeEnd, case_id], 1);
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
                        est_preg_end.setTime(est_preg_end.getTime() + 42*7*ms_day);
                        preg_end = est_preg_end.toISOString();
                    }

                    if (preg_start) {
                        var preg_start_date = new Date(preg_start),
                            preg_end_date = new Date(preg_end),
                            form_date = new Date(meta.timeEnd);
                        var is_pregnant = ((form_date >= preg_start_date) && (form_date < preg_end_date));
                        if (is_pregnant)
                            emit([doc.domain, "visit pregnant", meta.timeEnd, case_id], 1);
                    }
                }
            }

        }
    }
}