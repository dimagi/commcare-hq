function(key, values, rereduce) {
  var earliest = null;
  var latest = null;

  for (var i in values) {
    var val = values[i];

    var _e = (rereduce ? val[0] : val);
    var _l = (rereduce ? val[1] : val);

    earliest = (earliest ? Math.min(_e, earliest) : _e);
    latest =   (latest ?   Math.max(_l, latest) :   _l);
  }
  return [earliest, latest];
}