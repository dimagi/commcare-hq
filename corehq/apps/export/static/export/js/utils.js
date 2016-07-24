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

    /**
     * readablePath
     *
     * Takes an array of PathNodes and converts them to a string dot path.
     *
     * @param {Array} pathNodes - An array of PathNodes to be converted to a string
     *      dot path.
     * @returns {string} A string dot path that represents the array of PathNodes
     */
    var readablePath = function(pathNodes) {
        return _.map(pathNodes, function(pathNode) {
            return pathNode.name();
        }).join('.')
    };

    /**
     * customPathToNodes
     *
     * This function takes a string path like form.meta.question and
     * returns the equivalent path in an array of PathNodes.
     *
     * @param {string} customPathString - A string dot path to be converted
     *      to PathNodes.
     * @returns {Array} Returns an array of PathNodes.
     */
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
