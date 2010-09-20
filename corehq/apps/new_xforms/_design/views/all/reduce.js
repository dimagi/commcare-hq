
function(xmlns, docs) {
    /* copied in from http://www.tutorialspoint.com/javascript/array_reduce.htm */
    docs.reduce = function(fun /*, initial*/)
    {
    var len = this.length;
    if (typeof fun != "function")
      throw new TypeError();

    // no value to return if no initial value and an empty array
    if (len == 0 && arguments.length == 1)
      throw new TypeError();

    var i = 0;
    if (arguments.length >= 2)
    {
      var rv = arguments[1];
    }
    else
    {
      do
      {
        if (i in this)
        {
          rv = this[i++];
          break;
        }

        // if array contains no values, no initial value to return
        if (++i >= len)
          throw new TypeError();
      }
      while (true);
    }

    for (; i < len; i++)
    {
      if (i in this)
        rv = fun.call(null, rv, this[i], i, this);
    }

    return rv;
    };

    var doc = eval(uneval(docs.reduce(function(x,y){
        if(Date(x['submit_time']) > Date(y['submit_time'])) {
            return x;
        }
        else {
            return y;
        }
    }, {'submit_time': 0})));

    /* doc['forms'] = [];

   for (var d in docs) {
        if(d['forms'] != undefined) {
            doc['forms'] = doc['forms'].concat(d['forms']);
        }
        else {
            doc['forms'].push(d['_id']);
        }
    }    */
    return doc;
}