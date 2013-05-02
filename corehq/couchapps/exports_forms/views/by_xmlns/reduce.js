function (key, values) {
    var value = null,
        submissions = 0,
        i;

    for(i = 0; i < values.length; i += 1) {
        submissions += values[i].submissions || 0;
        if (value === null) {
            value = values[i];
        } else if ((value.app && values[i].app) || value.duplicate || values[i].duplicate) {
            if (!(value.app && values[i].app)) {
                value = value.app ? value : values[i];
            } else if (value.app_deleted !== values[i].app_deleted) {
                // pick the one that's not deleted
                value = value.app_deleted ? values[i] : value;
            } else {
                // arbitrarily pick the one with the shortest app_name
                value = values[i].app.name.length > value.app.name.length ? value : values[i];
            }
            value.duplicate = true;
        } else if (!value.app && values[i].app) {
            value = values[i];
        }
    }
    value.submissions = submissions;
    return value;
}