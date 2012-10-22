function (doc) {
    // !code util/mvp.js
    if (isChildRegistrationForm(doc)) {
        var meta = doc.form.meta,
            indicator_keys = new Array();

        var reg_date = new Date(meta.timeEnd);

        indicator_keys.push("registration");
        if (doc.form.delivered_in_facility === 'yes') {
            indicator_keys.push("facility_delivery");
        }

        emit_standard(doc, reg_date, indicator_keys, []);
    }
}