function (doc) {
    // !code util/mvp.js
    if (isChildCloseForm(doc) ||
        isPregnancyCloseForm(doc)) {
        var indicators = get_indicators(doc),
            closed_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = new Array(),
            close_reason = "",
            termination_reason = "";

        if (indicators.close_reason && indicators.close_reason.value) {
            close_reason = indicators.close_reason.value;
        }

        if (indicators.termination_reason && indicators.termination_reason.value) {
            termination_reason = indicators.termination_reason.value;
        }

        if (isChildCloseForm(doc)
            && close_reason === 'death'
            && (indicators.date_of_death && indicators.date_of_death.value)
            && (indicators.child_dob && indicators.child_dob.value)) {
            var date_of_death = new Date(indicators.date_of_death.value),
                child_dob = new Date(indicators.child_dob.value);

            if (child_dob <= date_of_death) {
                var difference = date_of_death.getTime() - child_dob.getTime();
                if (difference <= 28*MS_IN_DAY) {
                    indicator_keys.push("neonatal_death");
                }
                if (difference < 330*MS_IN_DAY) {
                    indicator_keys.push("infant_death")
                }
                if (difference < 1860*MS_IN_DAY) {
                    indicator_keys.push("under5_death")
                }

            }
        }

        if (isPregnancyCloseForm(doc)
            && termination_reason === 'stillbirth') {
            indicator_keys.push("neonatal_death");
            indicator_keys.push("infant_death");
            indicator_keys.push("under5_death");
        }

        emit_standard(doc, closed_date, indicator_keys, []);
    }
}
