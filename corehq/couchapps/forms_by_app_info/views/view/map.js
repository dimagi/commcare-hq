function (doc) {
    if ( (doc.doc_type === "Application" || doc.doc_type === "Application-Deleted" || doc.doc_type === "LinkedApplication" || doc.doc_type === "LinkedApplication-Deleted")
        && doc.copy_of === null) {
        // all xforms bound to an application at some point in time
        var is_deleted = (doc.doc_type === 'Application-Deleted' || doc.doc_type === 'LinkedApplication-Deleted');
        var status = (is_deleted) ? "deleted" : "active";

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
                    emit(["status xmlns", doc.domain, status, form.xmlns], value);

                    emit(["xmlns app", doc.domain, form.xmlns, value.app.id || {}], value);
                    emit(["status xmlns app", doc.domain, status, form.xmlns, value.app.id || {}], value);

                    emit(["app module form", doc.domain, value.app.id || {}, value.module.id, value.form.id], value);
                    emit(["status app module form", doc.domain, status, value.app.id || {}, value.module.id, value.form.id], value);
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
                    emit(["status xmlns", doc.domain, status, reg_form.xmlns], reg_value);

                    emit(["xmlns app", doc.domain, reg_value.xmlns, reg_value.app.id || {}], reg_value);
                    emit(["status xmlns app", doc.domain, status, reg_value.xmlns, reg_value.app.id || {}], reg_value);

                    emit(["app module form", doc.domain, reg_value.app.id || {}, reg_value.module.id, reg_value.form.id], reg_value);
                    emit(["status app module form", doc.domain, status, reg_value.app.id || {}, reg_value.module.id, reg_value.form.id], reg_value);
                }
            }
        }

    }
}
