/**
 * @param exact_keys
 * @param range_keys
 * @param data hash of data keys and number, boolean, or list<number,boolean>
 *        values for those keys
 * @param extra_keys hash of data keys and arrays of extra values to include in
 *        the key for that data key
 */
function emit_array(exact_keys, range_keys, data, extra_keys) {
    extra_keys = extra_keys || {};

    for (var k in extra_keys) {
        if (typeof extra_keys[k] !== "object") {
            extra_keys[k] = [extra_keys[k]];
        }
    }

    for (var k in data) {
        if (data[k] !== null) {
            var _emit = function (val) {
                emit(exact_keys.concat([k])
                    .concat(range_keys)
                    .concat(extra_keys[k] || []),
                    val);
            };

            switch (typeof data[k]) {
                case 'boolean':
                    _emit(data[k] ? 1 : 0);
                    break;
                case 'object':  // array of numbers
                    for (var i in data[k]) {
                        _emit(data[k][i]);
                    }
                    break;
                case 'number':
                    _emit(data[k]);
                    break;
                // anything else is unsupported for builtin _stats view and
                // should error
            }
        }
    }
}
