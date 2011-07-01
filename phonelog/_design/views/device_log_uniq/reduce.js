function(keys, values, rereduce) {
  var strmin = function(sa, sb) { return (sa < sb ? sa : sb); };

  earliest = null;
  for (var i in values) {
    var t = values[i];
    earliest = (earliest ? strmin(earliest, t) : t);
  }
  return earliest;
}