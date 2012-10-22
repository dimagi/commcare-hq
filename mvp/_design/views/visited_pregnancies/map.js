function(doc) {
    // !code util/mvp.js
    if(isPregnancyVisitForm(doc)) {
        var indicators = get_indicators(doc),
            visit_date = new Date(doc.form.meta.timeEnd),
            case_id = get_case_id(doc),
            indicator_entries = {};

        if (indicators.pregnancy_edd && indicators.pregnancy_edd.value
            && indicators.pregnancy_end) {
            var is_currently_pregnant = true,
                edd_date = new Date(indicators.pregnancy_edd.value);
            var start_date = get_pregnancy_start_from_edd_date(edd_date);
            if (start_date > visit_date) {
                // Strange. Shouldn't happen. But Pregnancy of related case happened before this visit.
                is_currently_pregnant = false;
            }
            if (is_currently_pregnant && indicators.pregnancy_end.value) {
                var end_date = new Date(indicators.pregnancy_end.value);
                if (end_date <= visit_date) {
                    // pregnancy has ended.
                    is_currently_pregnant = false;
                }
            }
            if (is_currently_pregnant) {
                indicator_entries["pregnant"] = case_id;
            }
        }

        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}