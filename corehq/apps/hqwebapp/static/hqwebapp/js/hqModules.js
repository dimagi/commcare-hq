var COMMCAREHQ_MODULES = {};

function hqDefine(path, moduleAccessor) {
    var parts = ['COMMCAREHQ_MODULES'].concat(path.split('/'));
    var i;
    var object = window;
    for (i = 0; i < parts.length - 1; i += 1) {
        if (typeof object[parts[i]] === 'undefined') {
            object[parts[i]] = {};
        }
        object = object[parts[i]];
    }
    if (typeof object[parts[i]] !== 'undefined') {
        throw new Error("The module '" + path + "' has already been defined elsewhere.");
    }
    object[parts[i]] = moduleAccessor();
}

function hqImport(path) {
    var parts = ['COMMCAREHQ_MODULES'].concat(path.split('/'));
    var i;
    var object = window;
    for (i = 0; i < parts.length; i += 1) {
        object = object[parts[i]];
    }
    return object;
}
