Exports.Utils.getTagCSSClass = function(tag) {
    var cls = 'label';
    if (tag === Exports.Constants.TAG_DELETED) {
        return cls + ' label-warning';
    }
    return cls;
};

Exports.Utils.redirect = function(url) {
    window.location.href = url;
};

Exports.Utils.animateToEl = function(toElementSelector, callback) {
    $('html, body').animate({
        scrollTop: $(toElementSelector).offset().top + 'px'
    }, 'slow', undefined, callback);
};

Exports.Utils.removeDeidTransforms = function(transforms) {
    return _.filter(transforms, function(transform) {
        return _.values(Exports.Constants.DEID_OPTIONS).indexOf(transform) === -1;
    });
};

Exports.Utils.getTableName = function(path, exportType) {
    if (exportType === Exports.Constants.FORM_EXPORT) {
        if (JSON.stringify(path) === JSON.stringify(Exports.Constants.MAIN_TABLE)) {
            return gettext('Forms');
        } else if (path.length) {
            return gettext('Repeat: ') + path[path.length - 1];
        }
    } else if (exportType === Exports.Constants.CASE_EXPORT) {
        if (JSON.stringify(path) === JSON.stringify(Exports.Constants.MAIN_TABLE)) {
            return gettext('Cases');
        } else if (JSON.stringify(path) === JSON.stringify(Exports.Constants.CASE_HISTORY)) {
            return gettext('Case History');
        }
    }
    return gettext('Unknown');
};
