function(doc) {
  if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
    var recvd = doc.received_on.substring(0, 19);
    emit([doc.domain, doc.form.device_id, recvd);
  }
}