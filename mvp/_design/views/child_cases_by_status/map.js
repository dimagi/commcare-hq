function (doc) {
    // !code util/mvp.js
    if (isChildCase(doc)) {
        var case_id = get_case_id(doc),
            indicator_emit = {};

        if (doc.dob || doc.dob_calc) {
            var dob_date = new Date(doc.dob_calc || doc.dob);
            var emit_dates = {
                opened_on: dob_date
            };

            if (doc.closed_on) {
                // Cases that have been closed at some point
                var closed_on_date = new Date(doc.closed_on);
                indicator_emit["closed"] = [doc._id];
                emit_dates["closed_on"] = closed_on_date;
            } else {
                indicator_emit["open"] = [doc._id];
            }

            emit_by_status(doc, emit_dates, indicator_emit, [case_id]);
        }

    }
}