function(doc) {
  // !code util.js

  if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
    var recvd = doc.received_on.substring(0, 19);

    var logs = normalizeRepeats(doc.form.log_subreport.log);
    for (var i in logs) {
      var entry = logs[i];
      emit([doc.form.device_id, entry], recvd);
    }
  }
}
