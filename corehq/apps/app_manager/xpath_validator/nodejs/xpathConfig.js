if (typeof require !== 'undefined' && typeof exports !== 'undefined') {
    var parser = require('js-xpath/parser');
    var xpath = require('js-xpath/xpath');
}

var XPATH_CONFIG = (function () {
    function getAllowedHashtags(allowCaseHashtags) {
        var replacements = {
        '#session': "ok",
        '#user': "ok"
        };
        if (allowCaseHashtags) {
            replacements['#case'] = 'ok';
            replacements['#parent'] = 'ok';
            replacements['#host'] = 'ok';
        }
        return replacements;
    }

    function configureHashtags(allowCaseHashtags) {
        var p = new parser.Parser();
        p.setXPathModels = function(models) {
            p.yy.xpathmodels = models;
        };
        var replacements = getAllowedHashtags(allowCaseHashtags);
        p.setXPathModels(xpath.makeXPathModels({
            isValidNamespace: function (namespace) {
                return replacements.hasOwnProperty('#' + namespace);
            },
            hashtagToXPath: function (hashtagExpr) {
                if (replacements.hasOwnProperty(hashtagExpr)) {
                    return replacements[hashtagExpr];
                } else {
                    throw new Error("Invalid hashtag " + hashtagExpr);
                }
            },
            toHashtag: function (xpath_) {
                throw new Error("toHashtag not implemented");
            }
        }));
        return p;
    }
    return {'configureHashtags': configureHashtags};
}());

if (typeof require !== 'undefined' && typeof exports !== 'undefined') {
    exports.configureHashtags = XPATH_CONFIG.configureHashtags;
}
