/*
 * This test package is heavily adapted from the previous test suite:
 * https://bitbucket.org/javarosa/javarosa/src/tip/core/test/org/javarosa/xpath/test/XPathParseTest.java
 * 
 */

var runCommon = function(testcases) {
    for (var i in testcases) {
        if (testcases.hasOwnProperty(i)) {
            try {
                equal(xpath.parse(i).toString(), testcases[i], "" + i + " parsed correctly.");
            } catch(err) {
                ok(false, "" + err + " for input: " + i);
            }
        }
    }
};
                
var runFailures = function(testcases) {
    for (var i in testcases) {
        if (testcases.hasOwnProperty(i)) {
            var tmpFunc = function() {
                xpath.parse(i);
            }
            raises(tmpFunc, testcases[i], "" + i + " correctly failed to parse.");
        }
    }    
}

test("null expressions", function () {
    runFailures({
        "": null,
        "     ": null,
        "  \t \n  \r ": null
    });
});

test("numbers", function() {
    runCommon({
        "10": "{num:10}",
        "123.": "{num:123.}",
 		"734.04": "{num:734.04}",
		"0.12345": "{num:0.12345}",
		".666": "{num:0.666}",
		"00000333.3330000": "{num:333.333}",
		"1230000000000000000000": "{num:1230000000000000000000}",
		"1230000000000000000000.0": "{num:1.23e+21}",
		"0.00000000000000000123": "{num:1.23e-18}",
		"0": "{num:0}",
		"0.": "{num:0.}",
		".0": "{num:0.}",
		"0.0": "{num:0.}"
    });
});

test("strings", function () {
    runCommon({
        "\"\"": "{str:''}",
        "\"   \"": "{str:'   '}",
        "''": "{str:''}",
        "'\"'": "{str:'\"'}",
        "\"'\"": "{str:\"'\"}",
        "'mary had a little lamb'": "{str:'mary had a little lamb'}"
    });
    runFailures({
        "'unterminated string...": null,
    });
});


test("variables", function () {
    runCommon({
		"$var": "{var:var}",
		"$qualified:name": "{var:qualified:name}"
    });
    runFailures({
        "$x:*": null,
        "$": null,
        "$$asdf": null
    });
});

test("parens nesting", function () {
    runCommon({
        "(5)": "{num:5}",
        "(( (( (5 )) )))  ": "{num:5}",
    });
    runFailures({
        ")": null,
        "(": null,
        "()": null,
        "(((3))": null
    });
});

test("operators", function () {
    runCommon({
        "5 + 5": "{binop-expr:+,{num:5},{num:5}}",
        "-5": "{unop-expr:num-neg,{num:5}}",
        "- 5": "{unop-expr:num-neg,{num:5}}",
        "----5": "{unop-expr:num-neg,{unop-expr:num-neg,{unop-expr:num-neg,{unop-expr:num-neg,{num:5}}}}}",
        "6 * - 7": "{binop-expr:*,{num:6},{unop-expr:num-neg,{num:7}}}",
        "0--0": "{binop-expr:-,{num:0},{unop-expr:num-neg,{num:0}}}",             
        "5 * 5": "{binop-expr:*,{num:5},{num:5}}",
        "5 div 5": "{binop-expr:/,{num:5},{num:5}}",
        "5 mod 5": "{binop-expr:%,{num:5},{num:5}}",
        "3mod4": "{binop-expr:%,{num:3},{num:4}}",
        "3 mod6": "{binop-expr:%,{num:3},{num:6}}",
        "3mod 7": "{binop-expr:%,{num:3},{num:7}}",
        "5 divseparate-token": "{binop-expr:/,{num:5},{path-expr:rel,{{step:child,separate-token}}}}", //not quite sure if this is legal xpath or not, but it *can* be parsed unambiguously
        "5 = 5": "{binop-expr:==,{num:5},{num:5}}",
        "5 != 5": "{binop-expr:!=,{num:5},{num:5}}",
        "5 < 5": "{binop-expr:<,{num:5},{num:5}}",
        "5 <= 5": "{binop-expr:<=,{num:5},{num:5}}",
        "5 > 5": "{binop-expr:>,{num:5},{num:5}}",
        "5 >= 5": "{binop-expr:>=,{num:5},{num:5}}",
        "5 and 5": "{binop-expr:and,{num:5},{num:5}}",
        "5 or 5": "{binop-expr:or,{num:5},{num:5}}",
        "5 | 5": "{binop-expr:union,{num:5},{num:5}}"
    });
    runFailures({
        "+-": null,
        "5/5": null,
        "5%5": null,
        "5 == 5": null,
        "5 <> 5": null,
        ">=": null,
        "'asdf'!=": null
    });
});

test("operator associativity", function () {
    runCommon({
        "1 or 2 or 3": "{binop-expr:or,{num:1},{binop-expr:or,{num:2},{num:3}}}",
        "1 and 2 and 3": "{binop-expr:and,{num:1},{binop-expr:and,{num:2},{num:3}}}",
        "1 = 2 != 3 != 4 = 5": "{binop-expr:==,{binop-expr:!=,{binop-expr:!=,{binop-expr:==,{num:1},{num:2}},{num:3}},{num:4}},{num:5}}",
        "1 < 2 >= 3 <= 4 > 5": "{binop-expr:>,{binop-expr:<=,{binop-expr:>=,{binop-expr:<,{num:1},{num:2}},{num:3}},{num:4}},{num:5}}",
        "1 + 2 - 3 - 4 + 5": "{binop-expr:+,{binop-expr:-,{binop-expr:-,{binop-expr:+,{num:1},{num:2}},{num:3}},{num:4}},{num:5}}",
        "1 mod 2 div 3 div 4 * 5": "{binop-expr:*,{binop-expr:/,{binop-expr:/,{binop-expr:%,{num:1},{num:2}},{num:3}},{num:4}},{num:5}}",
        "1|2|3": "{binop-expr:union,{binop-expr:union,{num:1},{num:2}},{num:3}}",
        
    });
    
});

test("operator precedence", function () {
    runCommon({
        "1 < 2 = 3 > 4 and 5 <= 6 != 7 >= 8 or 9 and 10":
                "{binop-expr:or,{binop-expr:and,{binop-expr:==,{binop-expr:<,{num:1},{num:2}},{binop-expr:>,{num:3},{num:4}}},{binop-expr:!=,{binop-expr:<=,{num:5},{num:6}},{binop-expr:>=,{num:7},{num:8}}}},{binop-expr:and,{num:9},{num:10}}}",
        "1 * 2 + 3 div 4 < 5 mod 6 | 7 - 8":
                "{binop-expr:<,{binop-expr:+,{binop-expr:*,{num:1},{num:2}},{binop-expr:/,{num:3},{num:4}}},{binop-expr:-,{binop-expr:%,{num:5},{binop-expr:union,{num:6},{num:7}}},{num:8}}}",
        "- 4 * 6": "{binop-expr:*,{unop-expr:num-neg,{num:4}},{num:6}}",
        "6*(3+4)and(5or2)": "{binop-expr:and,{binop-expr:*,{num:6},{binop-expr:+,{num:3},{num:4}}},{binop-expr:or,{num:5},{num:2}}}",
    });
    runFailures({
        // disallowed by the xpath spec, but we don't care enough to catch this
        // "8|-9": null 
    });
});

test("function calls", function () {
    runCommon({
        "function()": "{func-expr:function,{}}",
        "func:tion()": "{func-expr:func:tion,{}}",
        "function(   )": "{func-expr:function,{}}",
        "function (5)": "{func-expr:function,{{num:5}}}",
        "function   ( 5, 'arg', 4 * 12)": "{func-expr:function,{{num:5},{str:'arg'},{binop-expr:*,{num:4},{num:12}}}}",
        "4andfunc()": "{binop-expr:and,{num:4},{func-expr:func,{}}}",
    });
    runFailures({
        "function ( 4, 5, 6 ": null,
    });
});


test("function calls that are actually node tests", function () {
    runCommon({
        "node()": "{path-expr:rel,{{step:child,node()}}}",
        "text()": "{path-expr:rel,{{step:child,text()}}}",
        "comment()": "{path-expr:rel,{{step:child,comment()}}}",
        "processing-instruction()": "{path-expr:rel,{{step:child,processing-instruction()}}}",
        "processing-instruction('asdf')": "{path-expr:rel,{{step:child,processing-instruction('asdf')}}}",
    });
    runFailures({
        "node(5)": null,
        "text('str')": null,
        "comment(name)": null,
        "processing-instruction(5)": null,
        "processing-instruction('asdf','qwer')": null,
        "child::func()": null,
    });
});

test("filter expressions", function () {
    runCommon({
        "bunch-o-nodes()[3]": "{filt-expr:{func-expr:bunch-o-nodes,{}},{{num:3}}}",
        "bunch-o-nodes()[3]['predicates'!='galore']": "{filt-expr:{func-expr:bunch-o-nodes,{}},{{num:3},{binop-expr:!=,{str:'predicates'},{str:'galore'}}}}",
        "(bunch-o-nodes)[3]": "{filt-expr:{path-expr:rel,{{step:child,bunch-o-nodes}}},{{num:3}}}",
        "bunch-o-nodes[3]": "{path-expr:rel,{{step:child,bunch-o-nodes,{{num:3}}}}}",
    });
    runFailures({});
});

test("path steps", function () {
    runCommon({
        ".": "{path-expr:rel,{{step:self,node()}}}",
        "..": "{path-expr:rel,{{step:parent,node()}}}",
    });
    runFailures({
        "..[4]": null,
        "preceding::..": null,
    });
});

test("name tests", function () {
    runCommon({
        "name": "{path-expr:rel,{{step:child,name}}}",
        "qual:name": "{path-expr:rel,{{step:child,qual:name}}}",
        "_rea--ll:y.funk..y_N4M3": "{path-expr:rel,{{step:child,_rea--ll:y.funk..y_N4M3}}}",
        "namespace:*": "{path-expr:rel,{{step:child,namespace:*}}}",
        "*": "{path-expr:rel,{{step:child,*}}}",
        "*****": "{binop-expr:*,{binop-expr:*,{path-expr:rel,{{step:child,*}}},{path-expr:rel,{{step:child,*}}}},{path-expr:rel,{{step:child,*}}}}",            
    });
    runFailures({
        "a:b:c": null,
        "inv#lid_N~AME": null,
        ".abc": null,
        "5abc": null,
    });
});

test("axes", function () {
    runCommon({
        "child::*": "{path-expr:rel,{{step:child,*}}}",
        "parent::*": "{path-expr:rel,{{step:parent,*}}}",
        "descendant::*": "{path-expr:rel,{{step:descendant,*}}}",
        "ancestor::*": "{path-expr:rel,{{step:ancestor,*}}}",
        "following-sibling::*": "{path-expr:rel,{{step:following-sibling,*}}}",
        "preceding-sibling::*": "{path-expr:rel,{{step:preceding-sibling,*}}}",
        "following::*": "{path-expr:rel,{{step:following,*}}}",
        "preceding::*": "{path-expr:rel,{{step:preceding,*}}}",
        "attribute::*": "{path-expr:rel,{{step:attribute,*}}}",
        "namespace::*": "{path-expr:rel,{{step:namespace,*}}}",
        "self::*": "{path-expr:rel,{{step:self,*}}}",
        "descendant-or-self::*": "{path-expr:rel,{{step:descendant-or-self,*}}}",
        "ancestor-or-self::*": "{path-expr:rel,{{step:ancestor-or-self,*}}}",
        "@attr": "{path-expr:rel,{{step:attribute,attr}}}",
        "@*": "{path-expr:rel,{{step:attribute,*}}}",
        "@ns:*": "{path-expr:rel,{{step:attribute,ns:*}}}",
    });
    runFailures({
        "bad-axis::*": null,
        "::*": null,
        "child::.": null,
        "@attr::*": null
    });
});

test("predicates", function () {
    runCommon({
        "descendant::node()[@attr='blah'][4]": "{path-expr:rel,{{step:descendant,node(),{{binop-expr:==,{path-expr:rel,{{step:attribute,attr}}},{str:'blah'}},{num:4}}}}}",
    });
    runFailures({
        "[2+3]": null,
    });
});

test("paths", function () {
    runCommon({
        "rel/ative/path": "{path-expr:rel,{{step:child,rel},{step:child,ative},{step:child,path}}}",
        "/abs/olute/path['etc']": "{path-expr:abs,{{step:child,abs},{step:child,olute},{step:child,path,{{str:'etc'}}}}}",
        "filter()/expr/path": "{path-expr:{filt-expr:{func-expr:filter,{}},{}},{{step:child,expr},{step:child,path}}}",
        "fil()['ter']/expr/path": "{path-expr:{filt-expr:{func-expr:fil,{}},{{str:'ter'}}},{{step:child,expr},{step:child,path}}}",
        "(another-filter)/expr/path": "{path-expr:{filt-expr:{path-expr:rel,{{step:child,another-filter}}},{}},{{step:child,expr},{step:child,path}}}",
        "/": "{path-expr:abs,{}}",
        "//all": "{path-expr:abs,{{step:descendant-or-self,node()},{step:child,all}}}",
        "a/.//../z": "{path-expr:rel,{{step:child,a},{step:self,node()},{step:descendant-or-self,node()},{step:parent,node()},{step:child,z}}}",
        "6andpath": "{binop-expr:and,{num:6},{path-expr:rel,{{step:child,path}}}}",
    
    });
    runFailures({
        "rel/ative/path/": null,
        "filter-expr/(must-come)['first']": null,
        "//": null,
    });
});

test("real world examples", function () {
    runCommon({
        "/foo/bar = 2.0": "{binop-expr:==,{path-expr:abs,{{step:child,foo},{step:child,bar}}},{num:2.}}",
        "/patient/sex = 'male' and /patient/age > 15": "{binop-expr:and,{binop-expr:==,{path-expr:abs,{{step:child,patient},{step:child,sex}}},{str:'male'}},{binop-expr:>,{path-expr:abs,{{step:child,patient},{step:child,age}}},{num:15}}}",
        "../jr:hist-data/labs[@type=\"cd4\"]": "{path-expr:rel,{{step:parent,node()},{step:child,jr:hist-data},{step:child,labs,{{binop-expr:==,{path-expr:rel,{{step:attribute,type}}},{str:'cd4'}}}}}}",
        "function_call(26*(7+3), //*, /im/child::an/ancestor::x[3][true()]/path)": "{func-expr:function_call,{{binop-expr:*,{num:26},{binop-expr:+,{num:7},{num:3}}},{path-expr:abs,{{step:descendant-or-self,node()},{step:child,*}}},{path-expr:abs,{{step:child,im},{step:child,an},{step:ancestor,x,{{num:3},{func-expr:true,{}}}},{step:child,path}}}}}"             
    });
});

test("template", function () {
    runCommon({});
    runFailures({});
});
