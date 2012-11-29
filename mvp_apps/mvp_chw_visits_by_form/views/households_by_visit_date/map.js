function(doc) {
    // !code util/mvp.js
    if(isHomeVisitForm(doc)) {
        var meta = doc.form.meta;
        if (meta.timeEnd) {
            var visit_date = new Date(meta.timeEnd),
                indicator_keys = ["visit"];

            emit_standard(doc, visit_date, indicator_keys, [doc._id]);
        }
    }
}