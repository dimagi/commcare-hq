function (doc) {
    // !code util/mvp.js
    if (isHomeVisitForm(doc)) {
        var meta = doc.form.meta,
            indicators = get_indicators(doc),
            case_id = get_case_id(doc),
            indicator_emits = {},
            num_medicated = 0;

        var visit_date = new Date(meta.timeEnd);

        if (indicators.num_other_positive) {
            try {
                var num_positive = (indicators.num_other_positive.value) ? parseInt(indicators.num_other_positive.value) : 0;
                indicator_emits["over5_positive_rdt"] = num_positive;

                if (num_positive > 0 && indicators.num_antimalarials_other) {
                    num_medicated = (indicators.num_antimalarials_other.value) ? parseInt(indicators.num_antimalarials_other.value) : 0;
                    indicator_emits["over5_positive_rdt_medicated"] = num_medicated;
                }
            } catch (e) {
                log("could not parse num_other_positive or num_antimalarials_other");
            }
        }

        emit_special(doc, visit_date, indicator_emits, []);
    }
}
