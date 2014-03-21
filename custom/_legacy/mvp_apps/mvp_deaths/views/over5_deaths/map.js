function (doc) {
    // !code util/mvp.js
    if (isDeathWithoutRegistrationForm(doc)) {
        var indicators = get_indicators(doc),
            report_date;

        if (indicators.date_of_death && indicators.date_of_death.value) {
            report_date = new Date(indicators.date_of_death.value);
        } else {
            report_date = new Date(doc.form.meta.timeEnd);
        }

        var indicator_keys = ["over5_death"];
        //death_date = new Date(doc.form.meta.timeEnd);

        emit_standard(doc, report_date, indicator_keys, []);
    }
}
