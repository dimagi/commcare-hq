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
