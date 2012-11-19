function (doc) {
    if ( (doc.doc_type === "Application" || doc.doc_type === "Application-Deleted")
        && doc.copy_of === null) {
        // all xforms bound to an application at some point in time
        var is_deleted = doc.doc_type === 'Application-Deleted';

        for (var m = 0; m < doc.modules.length; m++) {
            var module = doc.modules[m];
            for (var f = 0; f < module.forms.length; f ++) {
                var form = module.forms[f];
                if (form.xmlns) {
                    var value = {
                        xmlns: form.xmlns,
                        app: {
                            names: doc.name,
                            langs: doc.langs,
                            id: doc._id
                        },
                        module: {
                            names: module.name,
                            id: m
                        },
                        form: {
                            names: form.name,
                            id: f
                        },
                        is_deleted: is_deleted
                    };
                    emit(["xmlns", doc.domain, form.xmlns], value);
                    emit(["app", doc.domain, value.app.id], value);
                    emit(["app xmlns", doc.domain, value.app.id, form.xmlns], value);
                    emit(["app module", doc.domain, value.app.id, value.module.id], value);
                    emit(["app module form", doc.domain, value.app.id, value.module.id, value.form.id], value);
                }
            }
            if (doc.user_registration) {
                var reg_form = doc.user_registration;
                if (reg_form.xmlns) {
                    var reg_value = {
                        xmlns: reg_form.xmlns,
                        app: {
                            names: doc.name,
                            langs: doc.langs,
                            id: doc._id
                        },
                        module: {
                            names: "User Registration",
                            id: -1
                        },
                        form: {
                            names: "User Registration Form",
                            id: 0
                        },
                        is_user_registration: true,
                        is_deleted: is_deleted
                    };
                    emit(["xmlns", doc.domain, reg_form.xmlns], reg_value);
                    emit(["app", doc.domain, reg_value.app.id], reg_value);
                    emit(["app xmlns", doc.domain, reg_value.app.id], reg_value);
                    emit(["app module", doc.domain, reg_value.app.id, reg_value.module.id], reg_value);
                    emit(["app module form", doc.domain, reg_value.app.id, reg_value.module.id, reg_value.form.id], reg_value);
                }
            }
        }

    }
}