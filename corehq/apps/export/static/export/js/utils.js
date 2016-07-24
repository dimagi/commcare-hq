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

    var readablePath = function(pathNodes) {
        return _.map(pathNodes, function(pathNode) {
            return pathNode.name();
        }).join('.')
    };

    var customPathToNodes = function(customPathString) {
        var models = hqImport('export/js/models.js');
        var parts = customPathString.split('.');
        return _.map(parts, function(part) {
            return new models.PathNode({
                name: part,
                is_repeat: false,
                doc_type: 'PathNode',
            });
        });
    };

    return {
        getTagCSSClass: getTagCSSClass,
        redirect: redirect,
        animateToEl: animateToEl,
        readablePath: readablePath,
        customPathToNodes: customPathToNodes,
    };
});
