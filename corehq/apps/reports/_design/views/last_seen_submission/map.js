function(doc) {
    function get_user_id(xform_doc) {
        var meta = xform_doc.form.meta;
        if (meta) return meta.userID;
    }
    function get_app_id(xform_doc) {
        if (doc.app_id) {
            return doc.app_id;
        } else {
            var meta = xform_doc.form.meta;
            if (meta && meta.appVersion) return meta.appVersion;
        }
        return null;
    }
    if(doc.doc_type == "XFormInstance" && get_user_id(doc) != null) {
        emit([doc.domain, get_user_id(doc), doc.received_on], {
            time: doc.received_on,
            xmlns: doc.xmlns,
            app_id: get_app_id(doc),
            user_id: (doc.form.meta ? doc.form.meta.userID : null),
            username: (doc.form.meta ? doc.form.meta.username : null)
        });
    }
}