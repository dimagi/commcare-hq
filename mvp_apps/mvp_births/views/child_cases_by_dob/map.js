function(doc) {
    // !code util/mvp.js
    if (isChildCase(doc) && (doc.dob_calc || doc.dob)) {
        var birth_date = new Date(doc.dob_calc || doc.dob),
            indicator_keys = new Array();

        indicator_keys.push("dob");

        emit_standard(doc, birth_date, indicator_keys, [doc._id]);
    }
}
