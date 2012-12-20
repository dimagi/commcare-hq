function (doc) {
    // !code util/mvp.js
    if (isPregnancyCase(doc)) {
        if (doc.edd_calc) {
            var edd_date = new Date(doc.edd_calc);
            emit_standard(doc, edd_date, ["pregnancy"], []);
        }
    }
}
