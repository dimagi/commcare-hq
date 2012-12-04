function (doc) {
    // !code util/mvp.js
    if (isChildCloseForm(doc) && hasIndicators(doc)) {
        var indicators = get_indicators(doc),
            death_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = new Array();

        if (indicators.date_of_death && indicators.date_of_death.value) {
            death_date = new Date(indicators.date_of_death.value);
        }

        if (indicators.child_dob && indicators.child_dob.value) {
            var date_of_birth = new Date(indicators.child_dob.value);
            var lifespan = death_date.getTime() - date_of_birth.getTime();

            if (lifespan <= 28*MS_IN_DAY) {
                indicator_keys.push("neonatal_death");
            }
            if (lifespan <= 220*MS_IN_DAY) {
                indicator_keys.push("infant_death");
            }
            if (lifespan <= 720*MS_IN_DAY) {
                indicator_keys.push("under5_death");
            }
        }
        emit_standard(doc, death_date, indicator_keys, []);
    }
}
