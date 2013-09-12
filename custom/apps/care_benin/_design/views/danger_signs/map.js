function(doc) {
    // !code util/forms_checks.js
    // !code util/care_form.js
    // !code util/emit_array.js

    if (isCAREForm(doc)){
        var form = new CareForm(doc);
        form.danger_signs(false);
    }
}