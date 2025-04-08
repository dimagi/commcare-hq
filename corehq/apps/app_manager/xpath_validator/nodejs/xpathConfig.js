/* eslint-env node */
if (typeof require !== 'undefined' && typeof exports !== 'undefined') {
    var parser = require('xpath/src/parser');
    var xpath = require('xpath/dist/js-xpath');
    var _ = require('underscore');
}

const XPATH_CONFIG = (function () {
    function getAllowedHashtags(allowCaseHashtags) {
        var replacements = {
            '#session': "ok",
            '#user': "ok",
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
        p.setXPathModels = function (models) {
            p.yy.xpathmodels = models;
        };
        var replacements = getAllowedHashtags(allowCaseHashtags);
        p.setXPathModels(xpath.makeXPathModels({
            isValidNamespace: function (namespace) {
                return _.has(replacements, '#' + namespace);
            },
            hashtagToXPath: function (hashtagExpr) {
                if (_.has(replacements, hashtagExpr)) {
                    return replacements[hashtagExpr];
                } else {
                    throw new Error("Invalid hashtag " + hashtagExpr);
                }
            },
            toHashtag: function (xpath_) {              // eslint-disable-line no-unused-vars
                throw new Error("toHashtag not implemented");
            },
        }));
        return p;
    }
    return {'configureHashtags': configureHashtags};
}());

if (typeof require !== 'undefined' && typeof exports !== 'undefined') {
    exports.configureHashtags = XPATH_CONFIG.configureHashtags;
}
