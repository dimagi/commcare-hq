function (doc) {
    // !code util/mvp.js
    if (isHomeVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            case_id = get_case_id(doc),
            indicator_entries = {};

        var visit_date = new Date(meta.timeEnd);

        if (case_id) {
            if (indicators.num_using_fp && indicators.num_using_fp.value) {
                var num_using_fp = (indicators.num_using_fp.value) ? parseInt(indicators.num_using_fp.value) : 0;
                indicator_entries['num_fp'] = {
                    date: meta.timeEnd,
                    _id: case_id,
                    value: num_using_fp
                };
            }
            if (indicators.num_ec && indicators.num_ec.value) {
                var num_ec = (indicators.num_ec.value) ? parseInt(indicators.num_ec.value): 0;
                indicator_entries['num_ec'] = {
                    date: meta.timeEnd,
                    _id: case_id,
                    value: num_ec
                };
            }
        }
        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}