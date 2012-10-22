function(doc) {
    // !code util/mvp.js
    if(isChildVisitForm(doc)) {
        var indicators = get_indicators(doc),
            meta = doc.form.meta,
            visit_date = new Date(meta.timeEnd),
            case_id = get_case_id(doc),
            indicator_entries = {};

        if (indicators.child_dob && indicators.child_dob.value) {
            // birthdate found, is child under 5?
            var age = get_age_from_dob(indicators.child_dob.value, meta.timeEnd);
            if (age < 5) {
                indicator_entries["under5"] = case_id;
                var age_in_days = age*365;
                if (age_in_days < 31) {
                    // This under5 child is also neonate
                    indicator_entries["neonate"] = case_id;
                }
            }
        }
        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}