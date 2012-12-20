function get_user_id(xform_doc) {
    return (xform_doc.form.meta ? xform_doc.form.meta.userID : null);
}

function get_username(xform_doc) {
    return (xform_doc.form.meta ? xform_doc.form.meta.username : null);
}

function get_app_id(xform_doc) {
    try {
        if (xform_doc.app_id) {
            return xform_doc.app_id;
        } else {
            var meta = xform_doc.form.meta;
            if (meta && meta.appVersion) return meta.appVersion;
        }
    } catch (e) {
        // do nothing
    }
    return null;
}