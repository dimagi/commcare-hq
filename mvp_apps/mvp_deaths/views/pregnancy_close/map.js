 function (doc) {
    // !code util/mvp.js
    if (isPregnancyCloseForm(doc) && hasIndicators(doc)) {
        var indicators = get_indicators(doc),
            close_date = new Date(doc.form.meta.timeEnd),
            indicator_keys = new Array();

        if (indicators.close_reason && indicators.close_reason.value) {
            var days_from_termination_ms = 0;
            if (indicators.pregnancy_termination && indicators.pregnancy_termination.value) {
                var termination_date = new Date(indicators.pregnancy_termination.value);
                days_from_termination_ms = close_date.getTime() - termination_date.getTime();
            }
            if (indicators.close_reason.value.indexOf('died') >= 0 && days_from_termination_ms <= 42) {
                indicator_keys.push('maternal_death');
            }
        }
        emit_standard(doc, death_date, indicator_keys, []);
    }
}