function(key, values) {
    var value = null;
    for(var i in values) {
        if(values[i].duplicate) {
            return values[i];
        } else if(value == null) {
            value = values[i];
        } else if(value.app == null && values[i].app != null) {
            value = values[i];
        } else if(value.app != null && values[i].app != null) {
            return {xmlns: value.xmlns, duplicate: true};
        }
    }
    return value;
}