function (doc) {
    // !code util/mvp.js
    if (isPregnancyCase(doc)) {
        var case_id = get_case_id(doc),
            indicator_emit = {};

        if (doc.edd || doc.edd_calc) {
            var edd_date = new Date(doc.edd_calc || doc.edd);
            var pregnancy_start_date = get_pregnancy_start_from_edd_date(edd_date);
            var emit_dates = {
                opened_on: pregnancy_start_date
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