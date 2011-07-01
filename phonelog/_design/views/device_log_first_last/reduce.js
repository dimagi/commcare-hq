function(key, values, rereduce) {
  var strmin = function(sa, sb) { return (sa < sb ? sa : sb); };
  var strmax = function(sa, sb) { return (sa < sb ? sb : sa); };

  var earliest = null;
  var latest = null;

  for (var i in values) {
    var val = values[i];

    var _e = (rereduce ? val[0] : val);
    var _l = (rereduce ? val[1] : val);

    earliest = (earliest ? strmin(_e, earliest) : _e);
    latest =   (latest ?   strmax(_l, latest) :   _l);
  }
  return [earliest, latest];
}