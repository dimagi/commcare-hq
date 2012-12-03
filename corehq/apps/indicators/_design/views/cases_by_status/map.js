function (doc) {
    // !code util/indicators.js
    if (doc.doc_type === "CommCareCase" && doc.type) {
        var indicator_entries_open = {},
            indicator_entries_closed = {},
            opened_on_date = new Date(doc.opened_on);

        indicator_entries_open["opened_on"] = 1;
        emit_special(doc, opened_on_date, indicator_entries_open, [doc._id]);

        if (doc.closed_on) {
            var closed_on_date = new Date(doc.closed_on);
            indicator_entries_closed["closed_on"] = 1;
            emit_special(doc, closed_on_date, indicator_entries_closed, [doc._id]);
        }

    }
}