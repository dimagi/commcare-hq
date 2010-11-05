function(doc) {
  if (doc['@xmlns'] == 'http://code.javarosa.org/devicereport') {
    var recvd = Date.parse(doc['#received_on']);
    if (!recvd) {
      //ignore log entries from before we began tracking time received
      return;
    }
    recvd /= 1000.;

    for (var i in doc.log_subreport.log) {
      var entry = doc.log_subreport.log[i];
      entry['version'] = doc.app_version;

      //in a given transmission, logs should be sent in reverse-chron order
      emit([doc['device_id'], recvd, -i], entry);
    }
  }
}