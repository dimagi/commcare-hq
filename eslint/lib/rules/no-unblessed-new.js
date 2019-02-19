/**
 * @fileoverview Disallow new expect for specified objects.
 * @author Jenny Schweers
 */
"use strict";

//------------------------------------------------------------------------------
// Rule Definition
//------------------------------------------------------------------------------

module.exports = {
    meta: {
        docs: {
            description: "Disallow new except for specified objects.",
            category: "Best Practices",
            recommended: false,
        },
        schema: [
            {
                type: "array",
                items: {
                    type: "string",
                    minLength: 1,
                },
                uniqueItems: true,
            }
        ]
    },

    create: function(context) {
        let allowed = {};
        const optionAllowed = context.options[0];
        if (optionAllowed) {
            for (var i = 0; i < optionAllowed.length; i++) {
                allowed[optionAllowed[i]] = true;
            }
        }

        return {

            NewExpression(node) {
                if (!allowed[node.callee.name]) {
                    context.report({ node, message: "Rewrite " + node.callee.name + " in a functional style. See https://github.com/dimagi/js-guide/blob/master/migrating.md#moving-away-from-classical-inheritance" });
                }
            }

        };
    }
};
