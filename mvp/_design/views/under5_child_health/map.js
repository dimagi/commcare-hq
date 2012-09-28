function(doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta;

        if (indicators && indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 5?
            var age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd);
            if (age < 5) {
                var fever_medication = indicators.fever_medication.value,
                    rdt_result = indicators.rdt_result.value;

                var rdt_test_received = (rdt_result === 'positive' || rdt_result === 'negative'),
                    rdt_test_positive = (rdt_result === 'positive'),
                    rdt_not_available = (rdt_result === 'rdt_not_available' || rdt_result === 'rdt_not_conducted'),
                    fever_only = false,
                    antimalarial_received = (fever_medication && (fever_medication.indexOf('anti_malarial') >= 0
                                                                    || fever_medication.indexOf('coartem') >= 0));

                try {
                    var danger_signs = indicators.immediate_danger_sign.value.trim();
                    danger_signs = danger_signs.split(' ');
                    log(danger_signs);
                    if (danger_signs.indexOf('fever') >= 0 && danger_signs.length === 1) {
                        fever_only = true;
                    }
                } catch (err) {
                    log('did not process danger signs');
                    log(err);
                }

                if (fever_only && meta.timeEnd) {
                    var emit_keys = [],
                        category = "under5_fever ";

                    if (rdt_test_received)
                        emit_keys.push('rdt_test_received');
                    if (rdt_test_positive)
                        emit_keys.push('rdt_test_positive');
                    if (antimalarial_received)
                        emit_keys.push('anti_malarial');

                    log("EMIT KEY");
                    log(emit_keys);

                    var emit_string = "";
                    for (var k in emit_keys) {
                        emit_string += emit_keys[k] + " ";
                        emit([doc.domain, category+emit_string.trim(), meta.timeEnd], 1);
                    }

                    if (rdt_not_available) {
                        emit([doc.domain, category+"rdt_not_available", meta.timeEnd], 1)
                    }


                    emit([doc.domain, category.trim(), meta.timeEnd], 1);
                }
            }
        }
    }
}