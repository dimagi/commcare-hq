function (doc) {
    // !code util/mvp.js
    if (isChildRegistrationForm(doc)) {
        var meta = doc.form.meta,
            indicator_keys = new Array();

        var reg_date = new Date(meta.timeEnd),
            birth_weight = doc.form.weight_at_birth;

        indicator_keys.push("registration");
        if (doc.form.delivered_in_facility === 'yes') {
            indicator_keys.push("facility_delivery");
        }
        if (birth_weight) {
            indicator_keys.push("birth_weight");
            var weight = parseInt(birth_weight);
            if (weight < 2.5) {
                indicator_keys.push("birth_weight low");
            }
        }

        emit_standard(doc, reg_date, indicator_keys, []);
    }
}
