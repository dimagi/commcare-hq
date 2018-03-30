/**
 * @fileoverview Disallow new expect for specified objects.
 * @author Jenny
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
        for (var i = 0; i < context.options.length; i++) {
            allowed[context.options[i]] = 1;
        }

        return {

            NewExpression(node) {
                if (!allowed[node.callee.name]) {
                    context.report({ node, message: "Rewrite " + node.callee.name + " in a functional style" });
                }
            }

        };
    }
};
