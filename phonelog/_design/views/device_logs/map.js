function(doc) {
  function clone(obj){
    if(obj == null || typeof(obj) != 'object')
        return obj;

    var temp = obj.constructor(); // changed

    for(var key in obj)
        temp[key] = clone(obj[key]);
    return temp;
  }

  if (doc.xmlns == 'http://code.javarosa.org/devicereport') {
    var recvd = doc.received_on.substring(0, 19);

    for (var i in doc.form.log_subreport.log) {
      // need to clone because you can't set the property on the actual doc
      var entry = clone(doc.form.log_subreport.log[i]);
      entry.version = doc.form.app_version;

      //in a given transmission, logs should be sent in reverse-chron order
      emit([doc.form.device_id, recvd, -i], entry);
    }
  }
}