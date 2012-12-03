function (doc) {
    // !code util/mvp.js
    if (isChildCase(doc)) {
        var indicators = get_indicators(doc);

        // danger signs
        if (indicators.immediate_danger_sign && indicators.immediate_danger_sign.value
            && indicators.visit_hospital && indicators.visit_hospital.value) {
            var danger_signs = indicators.immediate_danger_sign.value,
                hospital_visits = indicators.visit_hospital.value;

            for (var d in danger_signs) {
                var danger_sign_data = danger_signs[d];
                var visit_danger_signs = get_danger_signs(danger_sign_data.value);
                if (visit_danger_signs.indexOf('fever') >= 0 && visit_danger_signs.length > 1) {
                    // complicated fever
                    var fever_date = new Date(danger_sign_data.timeEnd);
                    for (var h in hospital_visits) {
                        var hospital_visit_data = hospital_visits[h];
                        if (hospital_visit_data.value === 'yes') {
                            var hospital_date = new Date(hospital_visit_data.timeEnd);
                            if (hospital_date >= fever_date) {
                                emit_standard(doc, hospital_date, ["under5_complicated_fever facility_followup"], []);
                                break;
                            }
                        }
                    }
                }
            }
        }


    }
}