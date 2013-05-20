function(doc) {
    // !code util.js

    if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
        var logs = normalizeRepeats(doc.form.log_subreport.log);
        for (var i = 0; i < logs.length; i++) {
            var entry = logs[i];
            if (entry.type == 'login') {
                var user = entry.msg.substring(entry.msg.indexOf('-') + 1);
                emit([doc.domain, user], null);
            }
        }
        if (doc.form.user_subreport) {
            var users = normalizeRepeats(doc.form.user_subreport.user);
            for (var i = 0; i < users.length; i++) {
                var username = users[i].username;
                emit([doc.domain, username], null);
            }
        }
    }
}
