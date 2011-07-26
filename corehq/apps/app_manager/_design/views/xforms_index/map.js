function(doc) {
    if(doc.doc_type == 'Application' && !doc.copy_of) {
        var app = doc;
        function doEmit(form) {
            emit(form.unique_id, {
                "app_id": doc._id,
                "unique_id": form.unique_id
            });
        }
        doEmit(app.user_registration);
        for(var m in app.modules) {
            for(var f in app.modules[m].forms) {
                doEmit(app.modules[m].forms[f]);
            }
        }
    }
}