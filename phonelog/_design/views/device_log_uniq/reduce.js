function(keys, values, rereduce) {
  earliest = null;
  for (var i in values) {
    var t = values[i];
    earliest = (earliest ? Math.min(earliest, t) : t);
  }
  return earliest;
}