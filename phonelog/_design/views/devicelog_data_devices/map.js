function(doc) {
    if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
        emit([doc.domain, doc.form.device_id], null);
    }
}