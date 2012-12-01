function (doc) {
    // !code util/mvp.js
    if (isChildCase(doc)) {
        var indicator_entries_open = {},
            indicator_entries_closed = {};

        if (doc.dob || doc.dob_calc) {
            var dob_date = doc.dob_calc || doc.dob,
                opened_on_date = new Date(doc.opened_on);

            indicator_entries_open["opened_on"] = dob_date;
            emit_special(doc, opened_on_date, indicator_entries_open, [doc._id]);

            if (doc.closed_on) {
                var closed_on_date = new Date(doc.closed_on);
                indicator_entries_closed["closed_on"] = dob_date;
                emit_special(doc, closed_on_date, indicator_entries_closed, [doc._id]);
            }
        }
    }
}