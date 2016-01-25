function (doc) {
    var app = doc,
        m,
        module,
        f,
        form,
        value;
    if ((doc.doc_type === "Application" || doc.doc_type === "Application-Deleted") && doc.copy_of === null) {
        for (m = 0; m < app.modules.length; m += 1) {
            module = app.modules[m];
            for (f = 0; f < module.forms.length; f += 1) {
                form = module.forms[f];
                if (form.xmlns) {
                    value = {
                        xmlns: form.xmlns,
                        app: {name: app.name, langs: app.langs, id: app._id},
                        module: {name: module.name, id: m},
                        form: {name: form.name, id: f},
                        app_deleted: doc.doc_type === "Application-Deleted"
                    };
                    emit([app.domain, app._id, form.xmlns], value);
                    emit([app.domain, {}, form.xmlns], value);
                }
            }
        }
        if (app.user_registration) {
            form = app.user_registration;
            if (form.xmlns) {
                value = {
                    xmlns: form.xmlns,
                    app: {name: app.name, langs: app.langs, id: app._id},
                    is_user_registration: true,
                    app_deleted: doc.doc_type === "Application-Deleted"
                };
                emit([app.domain, app._id, form.xmlns], value);
                emit([app.domain, {}, form.xmlns], value);
            }
        }
    }
}
