if (!String.prototype.endsWith) {
    String.prototype.endsWith = function(searchString, position) {
        var subjectString = this.toString();
        if (typeof position !== 'number' || !isFinite(position) || Math.floor(position) !== position || position > subjectString.length) {
            position = subjectString.length;
        }
        position -= searchString.length;
        var lastIndex = subjectString.indexOf(searchString, position);
        return lastIndex !== -1 && lastIndex === position;
    };
}

hqDefine('export/js/utils', function() {
    var getTagCSSClass = function(tag) {
        var constants = hqImport('export/js/const');
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

    var capitalize = function(string) {
        return string.charAt(0).toUpperCase() + string.substring(1).toLowerCase();
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
            var name = pathNode.name();
            return ko.utils.unwrapObservable(pathNode.is_repeat) ? name + '[]' : name;
        }).join('.');
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
        var models = hqImport('export/js/models');
        var parts = customPathString.split('.');
        return _.map(parts, function(part) {
            var isRepeat = part.endsWith('[]');
            if (isRepeat) {
                part = part.slice(0, part.length - 2);  // Remove the [] from the end of the path
            }
            return new models.PathNode({
                name: part,
                is_repeat: isRepeat,
                doc_type: 'PathNode',
            });
        });
    };

    return {
        getTagCSSClass: getTagCSSClass,
        redirect: redirect,
        animateToEl: animateToEl,
        capitalize: capitalize,
        readablePath: readablePath,
        customPathToNodes: customPathToNodes,
    };
});
