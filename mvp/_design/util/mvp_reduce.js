var countUniqueEmit = function (keys, values, rereduce) {
    var emitted_values = {
        _total_unique: 0
    };

    function update_emitted(value, increment) {
        if (Object.keys(emitted_values).indexOf(value) < 0) {
            emitted_values._total_unique += 1;
            emitted_values[value] = 0;
        }
        emitted_values[value] += increment;
    }

    function update_total(value) {
        if ((typeof value === 'number') && Object.keys(emitted_values).length === 1) {
            emitted_values._total_unique += 1;
            return true;
        }
        return false;
    }

    if (rereduce) {
        for (var i in values) {
            var ag_value = values[i];
            if (!update_total(ag_value)) {
                for (var ag_key in ag_value) {
                    update_emitted(ag_key, ag_value[ag_key]);
                }
            }
        }
    } else {
        for (var j in values) {
            var value = values[j];
            if (!update_total(value)) {
                update_emitted(value, 1);
            }
        }
    }

    if (Object.keys(emitted_values).length === 1 || rereduce) {
        return emitted_values._total_unique;
    }
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