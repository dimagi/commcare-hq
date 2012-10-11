function(doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta;

        if (indicators && indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 5?
            var age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd);
            if (age < 5) {
                emit(["all", doc.domain, "under5", meta.timeEnd], 1);
                emit(["user", doc.domain, meta.userID, "under5", meta.timeEnd], 1);

                var fever_medication = indicators.fever_medication.value,
                    diarrhea_medication = indicators.diarrhea_medication.value,
                    rdt_result = indicators.rdt_result.value;

                var rdt_test_received = (rdt_result === 'positive' || rdt_result === 'negative'),
                    rdt_test_positive = (rdt_result === 'positive'),
                    rdt_test_negative = (rdt_result === 'negative'),
                    rdt_not_available = (rdt_result === 'rdt_not_available' || rdt_result === 'rdt_not_conducted'),
                    fever_only = false,
                    diarrhea_only = false,
                    antimalarial_received = (fever_medication && (fever_medication.indexOf('anti_malarial') >= 0
                                                                    || fever_medication.indexOf('coartem') >= 0)),
                    diarrhea_medication_received = (diarrhea_medication && diarrhea_medication.indexOf('ors') >= 0);

                try {
                    var danger_signs = indicators.immediate_danger_sign.value.trim().toLowerCase();
                    danger_signs = danger_signs.split(' ');
                    if (danger_signs.indexOf('fever') >= 0 && danger_signs.length === 1) {
                        fever_only = true;
                    }
                    if (danger_signs.indexOf('diarrhea') >= 0 && danger_signs.length === 1) {
                        diarrhea_only = true;
                    }
                    if (danger_signs.length > 0) {
                        emit(["all", doc.domain, "under5_danger_signs", meta.timeEnd], 1);
                        emit(["user", doc.domain, meta.userID, "under5_danger_signs", meta.timeEnd], 1);
                    }
                } catch (err) {
                    log('did not process danger signs');
                    log(err);
                }

                var category = "",
                    emit_keys = [];
                if (fever_only && meta.timeEnd) {
                    category = "under5_fever ";
                    if (rdt_test_received)
                        emit_keys.push('rdt_test_received');
                    if (rdt_test_positive)
                        emit_keys.push('rdt_test_positive');
                    else if (rdt_test_negative)
                        emit_keys.push('rdt_test_negative');
                    if (antimalarial_received)
                        emit_keys.push('anti_malarial');

                    if (rdt_not_available) {
                        emit(["all", doc.domain, category+"rdt_not_available", meta.timeEnd], 1)
                        emit(["user", doc.domain, meta.userID, category+"rdt_not_available", meta.timeEnd], 1)
                    }

                } else if (diarrhea_only && meta.timeEnd) {
                    category = "under5_diarrhea ";

                    if (diarrhea_medication_received)
                        emit_keys.push('ors');
                }

                if (category) {
                    var emit_string = "";
                    for (var k in emit_keys) {
                        emit_string += emit_keys[k] + " ";
                        emit(["all", doc.domain, category+emit_string.trim(), meta.timeEnd], 1);
                        emit(["user", doc.domain, meta.userID, category+emit_string.trim(), meta.timeEnd], 1);
                    }

                    emit(["all", doc.domain, category.trim(), meta.timeEnd], 1);
                    emit(["user", doc.domain, meta.userID, category.trim(), meta.timeEnd], 1);
                }
            }
        }
    }
}