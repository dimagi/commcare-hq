function (doc) {
    // !code util/mvp.js
    if (isDeathWithoutRegistrationForm(doc)) {
        var indicator_keys = ["over5_death"],
            death_date = new Date(doc.form.meta.timeEnd);

        emit_standard(doc, death_date, indicator_keys, []);
    }
}
