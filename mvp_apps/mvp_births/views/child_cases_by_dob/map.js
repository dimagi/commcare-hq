function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) && (doc.dob_calc || doc.dob)) {
        var seven_days_ms = 7*MS_IN_DAY,
            birth_date = new Date(doc.dob_calc || doc.dob),
            indicators = get_indicators(doc),
            indicator_keys = new Array();

        indicator_keys.push("dob");

        emit_standard(doc, birth_date, indicator_keys, [doc._id]);
    }
}