function(doc) {
    var currentTags = new Array();
    if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
        for (var i in doc.form.log_subreport.log) {
            var log_type = doc.form.log_subreport.log[i].type;
            if (log_type && currentTags.indexOf(log_type) == -1) {
                emit(log_type);
                currentTags.push(log_type);
            }

        }
    }
}