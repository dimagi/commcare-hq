function(doc) {
    // !code util/mvp.js
    // !code util/danger_signs.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta;
        var indicator_keys = [];
        if (indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 5?
            var age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd);
            if (age < 1825*MS_IN_DAY) {
                indicator_keys.push("under5");

                var fever_medication = indicators.fever_medication.value,
                    diarrhea_medication = indicators.diarrhea_medication.value,
                    rdt_result = (typeof indicators.rdt_result.value === 'string') ? indicators.rdt_result.value.toLowerCase() : indicators.rdt_result.value,
                    referral_type = indicators.referral_type.value;

                var rdt_test_received = (rdt_result === 'positive' || rdt_result === 'negative'),
                    rdt_test_positive = (rdt_result === 'positive'),
                    rdt_test_negative = (rdt_result === 'negative'),
                    rdt_not_available = (rdt_result === 'rdt_not_available'
                                         || rdt_result === 'not_available' || rdt_result === 'rdt_not_conducted'),
                    uncomplicated_fever = false,
                    complicated_fever = false,
                    diarrhea_only = false,
                    antimalarial_received = (fever_medication && (fever_medication.indexOf('anti_malarial') >= 0
                                                                    || fever_medication.indexOf('coartem') >= 0)),
                    diarrhea_medication_received = (diarrhea_medication && diarrhea_medication.indexOf('ors') >= 0),
                    zinc_received = (diarrhea_medication && diarrhea_medication.indexOf('zinc') >= 0);

                var danger_signs = [],
                    emergency_signs = [],
                    valid_referrals = ['emergency', 'basic', 'take_to_clinic'];

                try {
                    danger_signs = get_danger_signs(indicators.immediate_danger_sign.value);
                } catch (err) {
                    // pass
                }

                try {
                    emergency_signs = get_danger_signs(indicators.emergency_danger_sign.value);
                } catch (err) {
                    // pass
                }

                if ((danger_signs.indexOf('fever') >= 0) || (danger_signs.indexOf('sign-fever') >= 0) ) {
                    if (danger_signs.length === 1) {
                        uncomplicated_fever = true;
                    } else {
                        complicated_fever = true;
                    }
                }
                if ((danger_signs.indexOf('diarrhea') >= 0 && danger_signs.length === 1) ||
                    (danger_signs.indexOf('sign_diarrhea') >= 0 && danger_signs.length === 1)) {
                    diarrhea_only = true;
                }

                if (danger_signs.length > 0 || emergency_signs.length > 0) {
                    indicator_keys.push("under5_danger_signs");
                    if (referral_type && valid_referrals.indexOf(referral_type)) {
                        indicator_keys.push("under5_danger_signs_referred");
                    }
                }

                var category = "",
                    category_keys = [];
                if (uncomplicated_fever && meta.timeEnd && age > 180*MS_IN_DAY) {
                    category = "under5_fever ";
                    if (rdt_test_received)
                        category_keys.push('rdt_test_received');
                    if (rdt_test_positive)
                        category_keys.push('rdt_test_positive');
                    else if (rdt_test_negative)
                        category_keys.push('rdt_test_negative');
                    if (antimalarial_received) {
                        category_keys.push('anti_malarial');
                    }

                    if (rdt_not_available) {
                        indicator_keys.push(category+"rdt_not_available");
                    }

                } else if (complicated_fever && meta.timeEnd) {
                    category = "under5_complicated_fever ";

                    if (doc.form.patient_available.referral_given === 'yes' ||
                        (referral_type && valid_referrals.indexOf(referral_type) >= 0)) {
                        category_keys.push('referred');
                    }

                } else if (diarrhea_only && meta.timeEnd && age > 60*MS_IN_DAY) {
                    category = "under5_diarrhea ";

                    if (diarrhea_medication_received)
                        category_keys.push('ors');
                    if (zinc_received)
                        indicator_keys.push(category+"zinc");
                }

                if (category) {
                    var emit_string = "";
                    for (var k in category_keys) {
                        emit_string += category_keys[k] + " ";
                        indicator_keys.push(category+emit_string.trim());
                    }
                    indicator_keys.push(category.trim());
                }
                var visit_date = new Date(meta.timeEnd);

                emit_standard(doc, visit_date, indicator_keys, []);
            }
        }
    }
}
