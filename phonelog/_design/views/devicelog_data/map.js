function(doc) {
    function clone(obj){
        if(obj == null || typeof(obj) != 'object')
            return obj;
        var temp = obj.constructor(); // changed
        for(var key in obj)
            temp[key] = clone(obj[key]);
        return temp;
    }
    var error_tags = ['exception', 'rms-repair', 'rms-spill'],
        warning_tags = ['case-recreate', 'permissions_notify', 'time message'];
    if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
        var user_subreport_usernames = [];
        if (doc.form.user_subreport) {
            for (var i in doc.form.user_subreport.user) {
                user_subreport_usernames.push(doc.form.user_subreport.user[i].username);
            }
        }

        var logged_in_user = "unknown";
        for (var i in doc.form.log_subreport.log) {
            // need to clone because you can't set the property on the actual doc
            var entry = clone(doc.form.log_subreport.log[i]);
            entry.device_users = user_subreport_usernames;
            entry.version = doc.form.app_version;
            entry.device_id = doc.form.device_id;

            if(entry.type == 'login')
                logged_in_user = entry.msg.substring(entry.msg.indexOf('-') + 1);
            entry.user = logged_in_user;

            if (entry.type && entry['@date']) {
                // Basic
                emit([doc.domain, "basic", entry['@date']], entry);
                var is_error = (error_tags.indexOf(entry.type) >= 0),
                    is_warning = (warning_tags.indexOf(entry.type) >= 0);

                if (is_warning === true || is_error === true) {
                    entry.isWarning = is_warning;
                    entry.isError = is_error;
                    emit([doc.domain, "errors_only", logged_in_user, entry['@date']], entry);
                    emit([doc.domain, "all_errors_only", entry['@date']], entry);
                }

                // Single Parameters
                emit([doc.domain, "tag", entry.type, entry['@date']], entry);
                emit([doc.domain, "device", doc.form.device_id, entry['@date']], entry);

                // Coupled Parameters
                emit([doc.domain, "tag_device", entry.type, doc.form.device_id, entry['@date']], entry);
            }

        }
    }
}
