function (doc) {
    var app = doc,
        m,
        module,
        f,
        form,
        value;
    if (doc.doc_type === "Application" && doc.copy_of === null) {
        for (m = 0; m < app.modules.length; m += 1) {
            module = app.modules[m];
            for (f = 0; f < module.forms.length; f += 1) {
                form = module.forms[f];
                value = {
                    xmlns: form.xmlns,
                    app: {name: app.name, langs: app.langs, id: app._id},
                    module: {name: module.name, id: m},
                    form: {name: form.name, id: f}
                };
                emit([app.domain, form.xmlns, app._id], value);
                emit([app.domain, form.xmlns, null], value);
            }
        }
        if (app.user_registration) {
            form = app.user_registration;
            value = {
                xmlns: form.xmlns,
                app: {name: app.name, langs: app.langs, id: app._id},
                is_user_registration: true
            };
            emit([app.domain, form.xmlns, app._id], value);
            emit([app.domain, form.xmlns, null], value);
        }
    } else if (doc.doc_type === "XFormInstance") {
        emit([doc.domain, doc.xmlns, null], {
            xmlns: doc.xmlns
        });
    }
}