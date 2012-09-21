function(doc) {
    if(doc.doc_type === "XFormInstance"
        && doc.xmlns === 'http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A' ) {
        var definition = doc.computed_.mvp_indicators,
            namespace = "mvp_indicators",
            meta = doc.form.meta;
        if (definition.child_dob) {
            var time_end_date = new Date(meta.timeEnd),
                dob = new Date(definition.child_dob.value),
                ms_year = 24*60*60*1000*365;
            var age = (time_end_date.getTime() - dob.getTime())/ms_year;
            if (age < 5) {
                var danger_signs = doc.form.curr_danger_type.trim(),
                    rdt_received_text = doc.form.patient_available.referral_follow_on.referral_and_rdt,
                    rdt_result_text = doc.form.patient_available.referral_follow_on.rdt_result,
                    cur_meds_given = doc.form.cur_meds_given;

                if (typeof rdt_result_text === 'object')
                    rdt_result_text = rdt_result_text['#text'];
                if (typeof rdt_received_text === 'object')
                    rdt_received_text = rdt_received_text['#text'];
                danger_signs = (danger_signs) ? danger_signs.split(' ') : null;

                var uncomplicated_fever = (danger_signs
                                            && danger_signs.indexOf('fever') >= 0
                                            && danger_signs.length === 1),
                    rdt_received = (rdt_received_text === 'yes'),
                    rdt_positive = (rdt_result_text === 'positive'),
                    rdt_not_available = (rdt_result_text === 'rdt_not_available' || rdt_result_text === 'rdt_not_conducted'),
                    antimalarial_received = (cur_meds_given && cur_meds_given.indexOf('anti_malarial') >= 0);

                if (uncomplicated_fever) {
                    emit([doc.domain, namespace, "under5 uncomplicated_fever", meta.timeEnd], 1);
                    if (rdt_received) {
                        emit([doc.domain, namespace, "under5 uncomplicated_fever rdt_received", meta.timeEnd], 1);
                        if (rdt_positive)
                            emit([doc.domain, namespace, "under5 uncomplicated_fever rdt_received rdt_positive", meta.timeEnd], 1);
                    }
                    if (rdt_positive && antimalarial_received)
                        emit([doc.domain, namespace, "under5 uncomplicated_fever rdt_positive antimalarial_received", meta.timeEnd], 1);
                    if (rdt_not_available)
                        emit([doc.domain, namespace, "under5 uncomplicated_fever rdt_not_available", meta.timeEnd], 1);
                }
                if (rdt_positive && antimalarial_received)
                    emit([doc.domain, namespace, "under5 rdt_positive antimalarial_received", meta.timeEnd], 1);
            }
        }
    }
}