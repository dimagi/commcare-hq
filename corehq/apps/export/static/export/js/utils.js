Exports.Utils.getTagCSSClass = function(tag) {
    var cls = 'label';
    if (tag === Exports.Constants.TAG_DELETED) {
        return cls + ' label-warning';
    } else {
        return cls + ' label-default';
    }
};

Exports.Utils.redirect = function(url) {
    window.location.href = url;
};

Exports.Utils.animateToEl = function(toElementSelector, callback) {
    $('html, body').animate({
        scrollTop: $(toElementSelector).offset().top + 'px'
    }, 'slow', undefined, callback);
};
