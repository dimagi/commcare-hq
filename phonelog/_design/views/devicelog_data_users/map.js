function(doc) {
    if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
        for (var i in doc.form.log_subreport.log) {
            var entry = doc.form.log_subreport.log[i];
            if (entry.type == 'login') {
                var user = entry.msg.substring(entry.msg.indexOf('-') + 1);
                emit([doc.domain, user], null);
            }
        }
    }
}