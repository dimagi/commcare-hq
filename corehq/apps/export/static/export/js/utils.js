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
