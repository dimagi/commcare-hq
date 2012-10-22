function(doc) {
    // !code util/mvp.js
    if(isHomeVisitForm(doc)) {
        var visit_date = new Date(doc.form.meta.timeEnd),
            case_id = get_case_id(doc);

        var indicator_entries = {
            visited: case_id
        };

        emit_special(doc, visit_date, indicator_entries, [doc._id]);
    }
}