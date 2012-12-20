function (doc) {
    // !code util/mvp.js
    if (isHomeVisitForm(doc)) {
        var meta = doc.form.meta,
            case_id = get_case_id(doc),
            indicator_emits = {};

        var visit_date = new Date(meta.timeEnd);

        if (doc.form.num_other_positive) {
            try {
                var num_positive = (doc.form.num_other_positive) ? parseInt(doc.form.num_other_positive): 0;
                indicator_emits["over5_positive_rdt"] = {
                    _id: case_id,
                    value: num_positive
                };
                if (num_positive > 0 && doc.form.num_antimalarials_other) {
                    var num_medicated = (doc.form.num_antimalarials_other) ? parseInt(doc.form.num_antimalarials_other) : 0;
                    indicator_emits["over5_positive_rdt_medicated"] = {
                        _id: case_id,
                        value: num_medicated
                    };
                }
            } catch (e) {
                log("could not parse num_other_positive or num_antimalarials_other");
            }
        }

        emit_special(doc, visit_date, indicator_emits, []);
    }
}
