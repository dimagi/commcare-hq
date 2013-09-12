function(doc) {
    // !code util/forms_checks.js
    // !code util/care_case.js
    // !code util/emit_array.js

    if (isCAREWomanCase(doc)) {
        var cc = new CareCase(doc);
        cc.by_village();
    }
}