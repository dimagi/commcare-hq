function(doc) {
    // !code util.js

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
            var users = normalizeRepeats(doc.form.user_subreport.user);
            for (var i = 0; i < users.length; i++) {
                var username = users[i].username;
                user_subreport_usernames.push(username);
            }
        }

        var logged_in_user = "unknown";
        var logs = normalizeRepeats(doc.form.log_subreport.log);
        for (var i = 0; i < logs.length; i++) {
            // need to clone because you can't set the property on the actual doc
            var entry = clone(logs[i]);
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

                if (user_subreport_usernames.length !== 0) {
                  var usernames = user_subreport_usernames;
                } else {
                  var usernames = [logged_in_user];
                }

                // Single Parameters
                emit([doc.domain, "tag", entry.type, entry['@date']], entry);
                emit([doc.domain, "device", doc.form.device_id, entry['@date']], entry);
                emit([doc.domain, "user", usernames, entry['@date']], entry);

                // Coupled Parameters
                emit([doc.domain, "tag_device", entry.type, doc.form.device_id, entry['@date']], entry);
                emit([doc.domain, "tag_user", entry.type, usernames, entry['@date']], entry);
                emit([doc.domain, "user_device", usernames, doc.form.device_id, entry['@date']], entry);
                emit([doc.domain, "tag_user_device", entry.type, usernames, doc.form.device_id, entry['@date']], entry);
            }

        }
    }
}
