function(doc) {
  if (doc['@xmlns'] == 'http://code.javarosa.org/devicereport') {
    var recvd = Date.parse(doc['#received_on']);
    if (!recvd) {
      //ignore log entries from before we began tracking time received
      return;
    }
    recvd /= 1000.;

    emit(doc['device_id'], recvd);
  }
}