/**
 * @fileoverview Disallow new expect for specified objects.
 * @author Jenny Schweers
 */
"use strict";

//------------------------------------------------------------------------------
// Requirements
//------------------------------------------------------------------------------

var rule = require("../../../lib/rules/no-unblessed-new"),

    RuleTester = require("eslint").RuleTester;


//------------------------------------------------------------------------------
// Tests
//------------------------------------------------------------------------------

var ruleTester = new RuleTester();
ruleTester.run("no-unblessed-new", rule, {

    valid: [
        {
            code: 'var thing = new Thing();',
            options: [["Thing"]],
        },
    ],

    invalid: [
        {
            code: "var thing = new Thing();",
            errors: ["Rewrite Thing in a functional style"],
        }
    ]
});
