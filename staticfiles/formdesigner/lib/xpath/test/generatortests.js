/*
 * This test package is heavily adapted from the previous test suite:
 * https://bitbucket.org/javarosa/javarosa/src/tip/core/test/org/javarosa/xpath/test/XPathParseTest.java
 * 
 */

var runGeneratorTests = function(testcases) {
    var parsed;
    for (var i in testcases) {
        if (testcases.hasOwnProperty(i)) {
            try {
                parsed = xpath.parse(i);
                equal(parsed.toXPath(), testcases[i], "" + i + " generated correctly.");
                // It seems reasonable to expect that the generated xpath
                // should parse back to the same object, although this may 
                // not always hold true.
                equal(parsed.toString(), xpath.parse(parsed.toXPath()).toString(), "" + i + " produced same result when reparsed.");
            } catch(err) {
                ok(false, "" + err + " for input: " + i);
            }
        }
    }
};

test("generator numbers", function() {
    runGeneratorTests({
        "123.": "123.",
        "734.04": "734.04",
        "0.12345": "0.12345",
        ".666": "0.666",
        "00000333.3330000": "333.333",
        "1230000000000000000000": "1230000000000000000000",
        "0.00000000000000000123": "0.00000000000000000123",
        "0": "0",
        "0.": "0.",
        ".0": "0.",
        "0.0": "0."
    });
});


test("generator strings", function () {
    runGeneratorTests({
        "\"\"": "''",
        "\"   \"": "'   '",
        "''": "''",
        "'\"'": "'\"'",
        "\"'\"": "\"'\"",
        "'mary had a little lamb'": "'mary had a little lamb'"
    });
});

test("generator variables", function () {
    runGeneratorTests({
		"$var": "$var",
		"$qualified:name": "$qualified:name"
    });
});


test("generator parens nesting", function () {
    runGeneratorTests({
        "(5)": "5",
        "(( (( (5 )) )))  ": "5",
    });
});

test("generator operators", function () {
    runGeneratorTests({
        "5 + 5": "5 + 5",
        "-5": "-5",
        "- 5": "-5",
        "----5": "----5",
        "6 * - 7": "6 * -7",
        "0--0": "0 - -0",             
        "5 * 5": "5 * 5",
        "5 div 5": "5 div 5",
        "5 mod 5": "5 mod 5",
        "3mod4": "3 mod 4",
        "3 mod6": "3 mod 6",
        "3mod 7": "3 mod 7",
        "5 divseparate-token": "5 div separate-token", //not quite sure if this is legal xpath or not, but it *can* be parsed unambiguously
        "5 = 5": "5 = 5",
        "5 != 5": "5 != 5",
        "5 < 5": "5 < 5",
        "5 <= 5": "5 <= 5",
        "5 > 5": "5 > 5",
        "5 >= 5": "5 >= 5",
        "5 and 5": "5 and 5",
        "5 or 5": "5 or 5",
        "5 | 5": "5 | 5"
    });
});

test("generator operator associativity", function () {
    runGeneratorTests({
        "1 or 2 or 3": "1 or 2 or 3",
        "1 and 2 and 3": "1 and 2 and 3",
        "1 = 2 != 3 != 4 = 5": "1 = 2 != 3 != 4 = 5",
        "1 < 2 >= 3 <= 4 > 5": "1 < 2 >= 3 <= 4 > 5",
        "1 + 2 - 3 - 4 + 5": "1 + 2 - 3 - 4 + 5",
        "1 mod 2 div 3 div 4 * 5": "1 mod 2 div 3 div 4 * 5",
        "1|2|3": "1 | 2 | 3",
    });
    
});

test("generator operator precedence", function () {
    runGeneratorTests({
        "1 < 2 = 3 > 4 and 5 <= 6 != 7 >= 8 or 9 and 10": "1 < 2 = 3 > 4 and 5 <= 6 != 7 >= 8 or 9 and 10",
        "1 * 2 + 3 div 4 < 5 mod 6 | 7 - 8": "1 * 2 + 3 div 4 < 5 mod 6 | 7 - 8",
        "- 4 * 6": "-4 * 6",
        "6*(3+4)and(5or2)": "6 * (3 + 4) and (5 or 2)",
        "(1 - 2) - 3": "1 - 2 - 3",        
        "1 - (2 - 3)": "1 - (2 - 3)"
    });
});


test("generator function calls", function () {
    runGeneratorTests({
        "function()": "function()",
        "func:tion()": "func:tion()",
        "function(   )": "function()",
        "function (5)": "function(5)",
        "function   ( 5, 'arg', 4 * 12)": "function(5, 'arg', 4 * 12)",
        "4andfunc()": "4 and func()",
    });
});


test("generator function calls that are actually node tests", function () {
    runGeneratorTests({
        "node()": "node()",
        "text()": "text()",
        "comment()": "comment()",
        "processing-instruction()": "processing-instruction()",
        "processing-instruction('asdf')": "processing-instruction('asdf')",
    });
});

test("generator filter expressions", function () {
    runGeneratorTests({
        "bunch-o-nodes()[3]": "bunch-o-nodes()[3]",
        "bunch-o-nodes()[3]['predicates'!='galore']": "bunch-o-nodes()[3]['predicates'!='galore']",
        "(bunch-o-nodes)[3]": "(bunch-o-nodes)[3]",
        "bunch-o-nodes[3]": "bunch-o-nodes[3]",
    });
});

test("generator path steps", function () {
    runGeneratorTests({
        ".": ".",
        "..": "..",
    });
});

test("generator name tests", function () {
    runGeneratorTests({
        "name": "name",
        "qual:name": "qual:name",
        "_rea--ll:y.funk..y_N4M3": "_rea--ll:y.funk..y_N4M3",
        "namespace:*": "namespace:*",
        "*": "*",
        "*****": "* * * * *",
    });
});

test("generator axes", function () {
    runGeneratorTests({
        "child::*": "*",
        "parent::*": "parent::*",
        "descendant::*": "descendant::*",
        "ancestor::*": "ancestor::*",
        "following-sibling::*": "following-sibling::*",
        "preceding-sibling::*": "preceding-sibling::*",
        "following::*": "following::*",
        "preceding::*": "preceding::*",
        "attribute::*": "@*",
        "namespace::*": "namespace::*",
        "self::*": "self::*",
        "descendant-or-self::*": "descendant-or-self::*",
        "ancestor-or-self::*": "ancestor-or-self::*",
        "@attr": "@attr",
        "@*": "@*",
        "@ns:*": "@ns:*",
    });
});

test("generator predicates", function () {
    runGeneratorTests({
        "descendant::node()[@attr='blah'][4]": "descendant::node()[@attr = 'blah'][4]",
    });
});

test("generator paths", function () {
    runGeneratorTests({
        "rel/ative/path": "rel/ative/path",
        "/abs/olute/path['etc']": "/abs/olute/path['etc']",
        "filter()/expr/path": "filter()/expr/path",
        "fil()['ter']/expr/path": "fil()['ter']/expr/path",
        "(another-filter)/expr/path": "(another-filter)/expr/path",
        "/": "/",
        "//all": "//all",
        "a/.//../z": "a/.//../z",
        "6andpath": "6 and path",
    });
});

test("generator real world examples", function () {
    runGeneratorTests({
        "/patient/sex = 'male' and /patient/age > 15": "/patient/sex = 'male' and /patient/age > 15",
        "../jr:hist-data/labs[@type=\"cd4\"]": "../jr:hist-data/labs[@type = 'cd4']",
        "function_call(26*(7+3), //*, /im/child::an/ancestor::x[3][true()]/path)": "function_call(26 * (7 + 3), //*, /im/an/ancestor::x[3][true()]/path)",
    });
});

