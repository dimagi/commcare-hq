var countUniqueEmit = function (keys, values, rereduce) {
    var emitted_values = {
        _total_unique: 0,
        unique_emits: []
    };

    if (rereduce) {
        for (var i in values) {
            var ag_value = values[i];
            if (ag_value.unique_emits) {
                for (var e = 0; e < ag_value.unique_emits.length; e++) {
                    var emitted_val = ag_value.emits[e];
                    if (emitted_val && emitted_values.unique_emits.indexOf(emitted_val) < 0) {
                        emitted_values.unique_emits.push(emitted_val);
                    }
                    if (!emitted_val) {
                        log ("not emitted val");
                        log (emitted_val);
                        log (ag_value);
                        log ("--");
                    }
                }
            } else {
                log ("unique emits null");
                log (ag_value);
                log("--");
            }

        }
    } else {
        for (var j in values) {
            var value = values[j];
            if (emitted_values.unique_emits.indexOf(values) < 0) {
                // this value is not yet saved, so save it.
                emitted_values.unique_emits.push(value);
            }
        }
    }

    emitted_values._total_unique = emitted_values.unique_emits.length;

//    if (rereduce) {
//        return emitted_values._total_unique;
//    }
    return emitted_values;
};
var countLatestUniqueSum = function(keys, values, rereduce) {
    var calc = {
        _sum_unique: 0,
        unique_items: {}
    };

    function should_override(new_entry) {
        if (typeof new_entry === 'number') {
            return false;
        }
        if (new_entry._id in calc.unique_items) {
            var saved_entry = calc.unique_items[new_entry._id];
            var new_date = new Date(new_entry.date),
                saved_date = new Date(saved_entry.date);
            return (new_date > saved_date);
        }
        return true;
    }

    function save_entry(new_entry) {
        calc.unique_items[new_entry._id] = {
            value: new_entry.value,
            date: new_entry.date,
            _id: new_entry._id
        }
    }

    if (rereduce) {
        for (var i in values) {
            var ag_values = values[i];
            log(ag_values);
            for (var a in ag_values.unique_items) {
                if (should_override(ag_values.unique_items[a])) {
                    save_entry(ag_values.unique_items[a]);
                }
            }
        }
    } else {
        for (var j in values) {
            var r_entry = values[j];
            if (should_override(r_entry)) {
                save_entry(r_entry);
            }
        }
    }

    for (var id in calc.unique_items) {
        calc._sum_unique += calc.unique_items[id].value;
    }

    if (rereduce) {
        return calc._sum_unique;
    }
    return calc;

};