function(doc){
    if(doc.domain == 'factory' && (doc.doc_type == 'Application' || doc.doc_type == 'RemoteApp') && doc.copy_of == null) {
        modules = [];
        for(i in doc.modules) {
            forms = [];
            for (j in doc.modules[i].forms) {
                forms.push({
                    "id": j,
                    "name": eval(uneval(doc.modules[i].forms[j].name))
                });
            }
            modules.push({
                "id": i,
                "name": eval(uneval(doc.modules[i].name)),
                "forms": forms,
            });
        }
        emit(doc.name, {
            "doc_type": doc.doc_type,
            "version": doc.version,
            "id": doc._id,
            "name": doc.name,
            "modules": modules
        });
    }
}