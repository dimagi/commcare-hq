function(doc) {
  if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
    var recvd = doc.received_on.substring(0, 19);

    for (var i in doc.form.log_subreport.log) {
      var entry = doc.form.log_subreport.log[i];
      emit([doc.domain, doc.form.device_id, entry], recvd);
    }
  }
}