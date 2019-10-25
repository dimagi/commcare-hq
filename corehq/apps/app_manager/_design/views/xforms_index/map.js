function (doc) {
    var m, f;
    function doEmit(form) {
        emit(form.unique_id, {
            "app_id": doc._id,
            "unique_id": form.unique_id
        });
    }
    if (doc.copy_of) {
        return;
    }
    if (doc.doc_type === 'Application') {
        if (doc.user_registration) {
            doEmit(doc.user_registration);
        }
        for (m in doc.modules) {
            for (f in doc.modules[m].forms) {
                doEmit(doc.modules[m].forms[f]);
            }
        }
    }
}
