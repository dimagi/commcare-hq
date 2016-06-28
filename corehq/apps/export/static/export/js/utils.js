hqDefine('export/js/utils.js', function () {
    var getTagCSSClass = function(tag) {
        var constants = hqImport('export/js/const.js');
        var cls = 'label';
        if (tag === constants.TAG_DELETED) {
            return cls + ' label-warning';
        } else {
            return cls + ' label-default';
        }
    };

    var redirect = function(url) {
        window.location.href = url;
    };

    var animateToEl = function(toElementSelector, callback) {
        $('html, body').animate({
            scrollTop: $(toElementSelector).offset().top + 'px',
        }, 'slow', undefined, callback);
    };

    return {
        getTagCSSClass: getTagCSSClass,
        redirect: redirect,
        animateToEl: animateToEl,
    };
});
