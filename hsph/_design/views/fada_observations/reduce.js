function (key, values, rereduce) {
    // All emitted values are booleans.
    // The only useful reduces are:
    //
    //  - group=false with a key that includes up to and including process_sbr_no
    //  - using group_level so a reduce is run for each different key up to and
    //    including process_sbr_no
    //
    //  Therefore, we can use logical OR as the reduce function, because it
    //  would be meaningless anyway if you tried to reduce across multiple
    //  process_sbr_no.

    for (var i = 0; i < values.length; i++) {
        if (values[i]) {
            return true;
        }
    }

    return false;
}
