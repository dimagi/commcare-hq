function(doc) {
    // !code util.js

    var currentTags = new Array();
    if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
        var logs = normalizeRepeats(doc.form.log_subreport.log);
        for (var i in logs) {
            var log_type = logs[i].type;
            if (log_type && currentTags.indexOf(log_type) == -1) {
                emit(log_type);
                currentTags.push(log_type);
            }

        }
    }
}
