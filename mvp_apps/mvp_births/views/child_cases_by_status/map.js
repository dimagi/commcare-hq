function (doc) {
    // !code util/mvp.js
    if (isChildCase(doc)) {
        var indicator_entries_open = {},
            indicator_entries_closed = {};

        var status = (doc.closed) ? "closed" : "open";

        if (doc.dob || doc.dob_calc) {
            var dob_date = doc.dob_calc || doc.dob,
                weight_at_birth = doc.weight_at_birth,
                opened_on_date = new Date(doc.opened_on);

            indicator_entries_open["opened_on"] = dob_date;
            indicator_entries_open["opened_on "+status] = dob_date;
            if (weight_at_birth) {
                try {
                    var weight = parseFloat(weight_at_birth);
                    if (weight < 2.5) {
                        indicator_entries_open["opened_on low_birth_weight"] = dob_date;
                    }
                } catch (e) {
                    // pass
                }
            }
            emit_special(doc, opened_on_date, indicator_entries_open, [doc._id]);

            if (doc.closed_on) {
                var closed_on_date = new Date(doc.closed_on);
                indicator_entries_closed["closed_on"] = dob_date;
                indicator_entries_closed["closed_on "+status] = dob_date;
                emit_special(doc, closed_on_date, indicator_entries_closed, [doc._id]);
            }
        }
    }
}
