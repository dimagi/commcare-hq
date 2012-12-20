function(doc) {
    // !code util/reports_forms.js

    if(doc.doc_type === "XFormInstance" && get_user_id(doc) != null) {
        if (doc.form.hasOwnProperty('@name')) {
            var form_name = doc.form['@name'];
            if (form_name) {
                emit(["xmlns", doc.domain, doc.xmlns, form_name], form_name);
                emit(["xmlns app", doc.domain, doc.xmlns, doc.app_id || {}, form_name], form_name);
            }
        }
    }
}
