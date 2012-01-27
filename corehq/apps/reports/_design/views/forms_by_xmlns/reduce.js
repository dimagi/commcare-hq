function (key, values) {
    var value = null,
        submissions = 0,
        i;

    for(i = 0; i < values.length; i += 1) {
        submissions += values[i].submissions || 0;
        if(value == null || values[i].duplicate) {
            value = values[i];
        } else if(value.duplicate) {
            // do nothing
        } else if(value.app == null && values[i].app != null) {
            value = values[i];
        } else if(value.app != null && values[i].app != null) {
            value = {xmlns: value.xmlns, duplicate: true};
        }
    }
    value.submissions = submissions;
    return value;
}