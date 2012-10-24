function (doc) {
    // !code util/mvp.js
    if (isChildCase(doc)) {
        var case_id = get_case_id(doc),
            indicator_emit_dob = {},
            indicator_emit = {};

        if (doc.dob || doc.dob_calc) {
            var dob_date = new Date(doc.dob_calc || doc.dob),
                opened_on_date = new Date(doc.opened_on);
            var emit_dates_dob = {
                opened_on: dob_date
            },
                emit_dates_opened = {
                opened_on: opened_on_date
            };

            var cur_muac = (doc.cur_muac) ? parseInt(doc.cur_muac): null;
            var is_gam_case = (cur_muac && cur_muac < 125);

            if (doc.closed_on) {
                // Cases that have been closed at some point
                var closed_on_date = new Date(doc.closed_on);
                indicator_emit_dob["closed dob"] = [doc._id];
                if (is_gam_case) {
                    indicator_emit["closed gam"] = [doc._id];
                }
                emit_dates_dob["closed_on"] = closed_on_date;
                emit_dates_opened["closed_on"] =closed_on_date;
            } else {
                indicator_emit_dob["open dob"] = [doc._id];
                if (is_gam_case) {
                    indicator_emit["open gam"] = [doc._id];
                }
            }

            emit_by_status(doc, emit_dates_dob, indicator_emit_dob, [case_id]);
            emit_by_status(doc, emit_dates_opened, indicator_emit, [case_id]);
        }

    }
}