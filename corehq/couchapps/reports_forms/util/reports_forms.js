function get_user_id(xform_doc) {
    return (xform_doc.form.meta ? xform_doc.form.meta.userID : null);
}

function get_username(xform_doc) {
    return (xform_doc.form.meta ? xform_doc.form.meta.username : null);
}

var MISSING_APP_ID = "_MISSING_APP_ID";

function get_app_id(xform_doc) {
    return xform_doc.app_id || MISSING_APP_ID;
}


