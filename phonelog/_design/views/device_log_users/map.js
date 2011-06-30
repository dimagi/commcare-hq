function(doc) {
  if (doc['@xmlns'] == 'http://code.javarosa.org/devicereport') {
    for (var i in doc.log_subreport.log) {
      var entry = doc.log_subreport.log[i];
      if (entry['type'] == 'login') {
        var user = entry['msg'].substring(entry['msg'].indexOf('-') + 1);
        if (user != 'admin') {
          emit([doc['device_id'], user], null);
        }
      }
    }
  }
}