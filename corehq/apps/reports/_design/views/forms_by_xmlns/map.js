function(doc){
    if(doc.doc_type == "Application" && doc.copy_of == null) {
        var app = doc;
        for(var m in app.modules) {
            var module = app.modules[m];
            for(var f in module.forms) {
                var form = module.forms[f];
                emit([app.domain, form.xmlns], {
                    xmlns: form.xmlns,
                    app: {name: app.name, langs: app.langs},
                    module: {name: module.name},
                    name: form.name
                });
            }
        }
    }
    else if(doc.doc_type == "XFormInstance") {
        emit([doc.domain, doc.xmlns], {
            xmlns: doc.xmlns
        });
    }
}