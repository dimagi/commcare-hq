if (typeof require !== 'undefined' && typeof exports !== 'undefined') {
    var Parser = require('js-xpath/parser').Parser;
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
        var parser = new Parser();
            parser.setXPathModels = function(models) {
            parser.yy.xpathmodels = models;
        };
        var replacements = getAllowedHashtags(allowCaseHashtags);
        parser.setXPathModels(xpath.makeXPathModels({
            isValidNamespace: function (namespace) {
                return replacements.hasOwnProperty('#' + namespace);
            },
            hashtagToXPath: function (hashtagExpr) {
                if (replacements.hasOwnProperty(hashtagExpr)) {
                    return replacements[hashtagExpr];
                } else {
                    throw new Error("This should be overridden");
                }
            },
            toHashtag: function (xpath_) {
                return xpath_.toXPath();
            }
        }));
        return parser;
    }
    return {'configureHashtags': configureHashtags};
}());

if (typeof require !== 'undefined' && typeof exports !== 'undefined') {
    exports.configureHashtags = XPATH_CONFIG.configureHashtags;
}
