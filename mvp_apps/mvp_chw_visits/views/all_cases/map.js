function (doc) {
    // !code util/mvp.js
    function emit_special_case_type(doc, emit_date, indicator_entries, suffix) {
        var user_id = get_user_id(doc);
        for (var key in indicator_entries) {
            var entry = indicator_entries[key];
            emit(smart_date_emit_key(["all", doc.domain, doc.type, key], emit_date, suffix), entry);
            emit(smart_date_emit_key(["user", doc.domain, doc.type, user_id, key], emit_date, suffix), entry);
        }
    }

    if (isHouseholdCase(doc) ||
        isChildCase(doc) ||
        isPregnancyCase(doc) ) {
        var indicator_entries_open = {},
            indicator_entries_closed = {},
            opened_on_date = new Date(doc.opened_on);

        indicator_entries_open["opened_on"] = 1;
        emit_special_case_type(doc, opened_on_date, indicator_entries_open, [doc._id]);

        if (doc.closed_on) {
            var closed_on_date = new Date(doc.closed_on);
            indicator_entries_closed["closed_on"] = 1;
            emit_special_case_type(doc, closed_on_date, indicator_entries_closed, [doc._id]);
        }

    }
}
