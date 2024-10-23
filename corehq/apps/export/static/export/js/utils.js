hqDefine('export/js/utils', [
    'jquery',
    'knockout',
    'underscore',
    'export/js/const',
], function (
    $,
    ko,
    _,
    constants
) {
    var getTagCSSClass = function (tag) {
        var cls = window.USE_BOOTSTRAP5 ? 'badge' : 'label';
        if (tag === constants.TAG_DELETED) {
            return cls + (window.USE_BOOTSTRAP5 ? ' text-bg-warning' : ' label-warning');
        } else {
            return cls + (window.USE_BOOTSTRAP5 ? ' text-bg-secondary' : ' label-default');
        }
    };

    var redirect = function (url) {
        window.location.href = url;
    };

    var animateToEl = function (toElementSelector, callback) {
        $('html, body').animate({
            scrollTop: $(toElementSelector).offset().top + 'px',
        }, 'slow', undefined, callback);
    };

    var capitalize = function (string) {
        return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
    };

    return {
        getTagCSSClass: getTagCSSClass,
        redirect: redirect,
        animateToEl: animateToEl,
        capitalize: capitalize,
    };
});
