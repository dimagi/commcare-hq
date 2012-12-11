 function (doc) {
    // !code util/mvp.js
    if (isPregnancyCloseForm(doc)) {
        var indicators = get_indicators(doc),
            close_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = new Array(),
            close_reason = "";

        if (indicators.close_reason && indicators.close_reason.value) {
            close_reason = indicators.close_reason.value;
        }

        if (close_reason.indexOf("died") >= 0
            && (indicators.pregnancy_termination && indicators.pregnancy_termination.value)) {
            // woman died and there is a termination date
            var termination_date = new Date(indicators.pregnancy_termination.value);
            if (close_date > termination_date) {
                var difference = close_date.getTime() - termination_date.getTime();
                if (difference <= 42*MS_IN_DAY) {
                    indicator_keys.push("maternal_death");
                }
            }
        }

        emit_standard(doc, close_date, indicator_keys, []);
    }
}
