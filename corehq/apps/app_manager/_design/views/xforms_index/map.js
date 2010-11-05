function(doc) {
    if(doc.doc_type == 'Application' && !doc.copy_of) {
        var app = doc;
        for(var m in app.modules) {
            for(var f in app.modules[m].forms) {
                emit(app.modules[m].forms[f].unique_id, {
                    "app_id": doc._id,
                    "module_id": parseInt(m),
                    "form_id": parseInt(f)
                })
            }
        }
    }
}