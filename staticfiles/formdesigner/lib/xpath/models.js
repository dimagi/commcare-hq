
/*
 * These models are very heavily based on their JavaRosa counterparts, which live at:
 * https://bitbucket.org/javarosa/javarosa/src/tip/core/src/org/javarosa/xpath/expr/
 * 
 */
xpathmodels = {};
xpathmodels.DEBUG_MODE = false;

debuglog = function () {
    if (xpathmodels.DEBUG_MODE) {
        console.log(arguments);   
    }
};
    
(function() {
    var xpm = xpathmodels;
    
	var validateAxisName = xpm.validateAxisName = function(name) {
	    for (var i in xpm.XPathAxisEnum) {
	        if (xpm.XPathAxisEnum.hasOwnProperty(i) && xpm.XPathAxisEnum[i] === name) {
	            return xpm.XPathAxisEnum[i];
	        }
	    }
	    throw name + " is not a valid axis name!";
	}
	
	// helper function
	var objToXPath = function(something) {
	    return something.toXPath();
	};
	
	xpm.XPathNumericLiteral = function(value) {
	    /*
	     * This is shockingly complicated for what should be simple thanks to 
	     * javascript number arithmetic.
	     * 
	     * Use the big number library to hold the value, which will hold
	     * large integers properly. For everything else, do the best rounding
	     * we can when exporting, since xpath doesn't like scientific notation
	     * 
	     */
	    this.value = SchemeNumber(value);
	    this.toString = function() {
	        return "{num:" + this.value.toString() + "}";
	    };
	    this.toXPath = function() {
	        // helper function
	        var toFixed = function (x) {
	          /*
	           * Convert scientific notation formatted numbers to their decimal
	           * counterparts
	           *
	           * HT: http://stackoverflow.com/questions/1685680/how-to-avoid-scientific-notation-for-large-numbers-in-javascript
	           */
	          var e;
	          if (x < 1.0) {
	            e = parseInt(x.toString().split('e-')[1]);
	            if (e) {
	                x *= Math.pow(10,e-1);
	                x = '0.' + (new Array(e)).join('0') + x.toString().substring(2);
	            }
	          } else {
	            e = parseInt(x.toString().split('+')[1]);
	            if (e > 20) {
	                e -= 20;
	                x /= Math.pow(10,e);
	                x += (new Array(e+1)).join('0');
	            }
	          }
	          return x;
	        };
	        return toFixed(this.value.toString());
	    };
	    this.getChildren = function () {
	       return [];
	    };
	    return this;
	};
	
	
	xpm.XPathStringLiteral = function(value) {
	    this.value = value; 
	    
	    var toXPathString = function(value) {
	        /*
	         * XPath doesn't support escaping, so all we do is check for quotation 
	         * marks and if we find them, use the other kind.
	         *  
	         */
	        if (value.indexOf("'") !== -1) {
	            // it has an apostrophe so wrap it in double quotes
	            return '"' + value + '"';
	        } else {
	            // it doesn't have an apostrophe so use single quotes, it could still
	            // have a double quote
	            return "'" + value + "'";
	        }
	    };
	    
	    this.valueDisplay = toXPathString(value);
	    this.toString = function() {
	        return "{str:" + this.valueDisplay + "}"; 
	    };
	    this.toXPath = function() {
	        return this.valueDisplay;
	    };
	    this.getChildren = function () {
           return [];
        };
        return this;
	};
	
	xpm.XPathVariableReference = function(value) {
	    this.value = value;
	    this.toString = function() {
	        return "{var:" + String(this.value) + "}";
	    };
	    this.toXPath = function() {
	        return "$" + String(this.value);
	    };
	    this.getChildren = function () {
           return [];
        };
	    
	};
	
	xpm.XPathAxisEnum = {
	    CHILD: "child",
	    DESCENDANT: "descendant",
	    PARENT: "parent",
	    ANCESTOR: "ancestor",
	    FOLLOWING_SIBLING: "following-sibling",
	    PRECEDING_SIBLING: "preceding-sibling",
	    FOLLOWING: "following",
	    PRECEDING: "preceding",
	    ATTRIBUTE: "attribute",
	    NAMESPACE: "namespace",
	    SELF: "self",
	    DESCENDANT_OR_SELF: "descendant-or-self",
	    ANCESTOR_OR_SELF: "ancestor-or-self"
	};
	
	xpm.XPathTestEnum = {
		NAME: "name", 
		NAME_WILDCARD: "*", 
		NAMESPACE_WILDCARD: ":*", 
		TYPE_NODE: "node()", 
		TYPE_TEXT: "text()", 
		TYPE_COMMENT: "comment()", 
		TYPE_PROCESSING_INSTRUCTION: "processing-instruction" 
	
	};
	
	    
	xpm.XPathStep = function(definition) {
		/*
		 * A step (part of a path)
		 * 
		 */        
	    this.axis = definition.axis;
	    this.test = definition.test;
	    this.predicates = definition.predicates || [];
	    this.name = definition.name;
	    this.namespace = definition.namespace;
	    this.literal = definition.literal;
	    
	    this.testString = function () {
	         switch(this.test) {
	            case xpm.XPathTestEnum.NAME:
	                return String(this.name);           
	            case xpm.XPathTestEnum.TYPE_PROCESSING_INSTRUCTION:
	                return "processing-instruction(" + (this.literal ? "\'" + this.literal + "\'" : "") + ")";
	            case xpm.XPathTestEnum.NAMESPACE_WILDCARD:
	                return this.namespace + ":*";
	            default:
	                return this.test || null;
	         }
	    };
	    
	    this.toString = function() {
	        var stringArray = [];
	                
	        stringArray.push("{step:");
		    stringArray.push(String(this.axis));
		    stringArray.push(",");
		    stringArray.push(this.testString());
		    if (this.predicates.length > 0) {
	            stringArray.push(",{");
	            stringArray.push(this.predicates.join(","));
	            stringArray.push("}");
		    }
		    
		    stringArray.push("}");
		    return stringArray.join("");
	    };
	    
	    this.mainXPath = function () {
	        var axisPrefix = this.axis + "::"; // this is the default
	        // Use the abbreviated syntax to shorten the axis
	        // or in some cases the whole thing
	        switch (this.axis) {
	            case xpm.XPathAxisEnum.DESCENDANT_OR_SELF:
	                if (this.test === xpm.XPathTestEnum.TYPE_NODE) {
	                    return "//";
	                }
	                break;
	            case xpm.XPathAxisEnum.CHILD:
	                axisPrefix = ""; // this is the default
	                break;
	            case xpm.XPathAxisEnum.ATTRIBUTE:
	                axisPrefix = "@";
	                break;
	            case xpm.XPathAxisEnum.SELF:
	                if (this.test === xpm.XPathTestEnum.TYPE_NODE) {
	                    return ".";
	                }
	                break;
	            case xpm.XPathAxisEnum.PARENT:
	                if (this.test === xpm.XPathTestEnum.TYPE_NODE) {
	                    return "..";
	                }
	                break;
	            default:
	               break;
	        }
	        return axisPrefix + this.testString();
	    };
	    this.predicateXPath = function () {
	        if (this.predicates.length > 0) {
	            return "[" + this.predicates.map(objToXPath).join("][") + "]"; 
	        }
	        return "";
	    };
	    this.toXPath = function() {
	        return this.mainXPath() + this.predicateXPath();
	    };
	    this.getChildren = function () {
           return [];
        };
        
	    return this;        
	};
	
	xpm.XPathInitialContextEnum = {
	    ROOT: "abs", 
	    RELATIVE: "rel", 
	    EXPR: "expr"
	};
	
	xpm.XPathPathExpr = function(definition) {
	    /**
	     * an XPath path, which consists mainly of steps
	     */
        var self = this;
        this.initial_context = definition.initial_context;
	    this.steps = definition.steps || [];
	    this.filter = definition.filter;
	    this.toString = function() {
	        var stringArray = [];
	        stringArray.push("{path-expr:");
	        stringArray.push(this.initial_context === xpm.XPathInitialContextEnum.EXPR ? 
	                         String(this.filter) : this.initial_context);
	        stringArray.push(",{");
	        stringArray.push(this.steps.join(","));
	        stringArray.push("}}");
	        return stringArray.join("");
	    };
	    var _combine = function (func) {
	        // this helper function only exists so that 
	        // the two methods below it can call itx
	        var parts = self.steps.map(func), ret = [], curPart, prevPart, sep;
            var root = (self.initial_context === xpm.XPathInitialContextEnum.ROOT) ? "/" : "";
            if (parts.length === 0) {
                return root;
            }
            for (var i = 0; i < parts.length; i ++) {
                curPart = parts[i];
                if (curPart !== "//" && prevPart !== "//") {
                    // unless the current part starts with a slash, put slashes between
                    // parts. the only exception to this rule is at the beginning, 
                    // when we only use a slash if it's an absolute path
                    sep = (i === 0) ? root : "/";
                    ret.push(sep);
                }
                ret.push(curPart);
                prevPart = curPart;
            }
            return ret.join(""); 
	    };
	    this.toXPath = function() {
            return _combine(objToXPath);
	    };
	    // custom function to pull out any filters and just return the root path
        this.pathWithoutPredicates = function() {
            return _combine(function (step) { return step.mainXPath(); });
        };
        
	    this.getChildren = function () {
           return this.steps;
        };
        
        
	    return this;
	};
	
	
	xpm.XPathFuncExpr = function (definition) {
		/**
		 * Representation of an xpath function expression.
		 */
	    this.id = definition.id;                 //name of the function
	    this.args = definition.args || [];       //argument list
	    this.toString = function() {
	        var stringArray = [];
	        stringArray.push("{func-expr:", String(this.id), ",{");
	        stringArray.push(this.args.join(","));
	        stringArray.push("}}");
	        return stringArray.join("");
	    };
	    this.toXPath = function() {
	        return this.id + "(" + this.args.map(objToXPath).join(", ") + ")";
	    };
	    this.getChildren = function () {
           return this.args;
        };
        return this;
	};
	
	
	// expressions
	
	xpm.XPathExpressionTypeEnum = {
	    /*
	     * These aren't yet really used anywhere, but they are correct.
	     * They correlate with the "type" field in the parser for ops.
	     * 
	     */
	    AND: "and", 
	    OR: "or",
	    EQ: "==",
	    NEQ: "!=",
	    LT: "<",
	    LTE: "<=",
	    GT: ">",
	    GTE: ">=",
	    PLUS: "+",
	    MINUS: "-",
	    MULT: "*",
	    DIV: "/",
	    MOD: "%",
	    UMINUS: "num-neg",
	    UNION: "union"
	};
	
	var expressionTypeEnumToXPathLiteral = xpm.expressionTypeEnumToXPathLiteral = function (val) {
	    switch (val) {
	        case xpm.XPathExpressionTypeEnum.EQ:
	            return "=";
	        case xpm.XPathExpressionTypeEnum.MOD:
	            return "mod";
	        case xpm.XPathExpressionTypeEnum.DIV:
	            return "div";
	        case xpm.XPathExpressionTypeEnum.UMINUS:
	            return "-";
	        case xpm.XPathExpressionTypeEnum.UNION:
	            return "|";
	        default:
	            return val;
	    }
	};
	
	var binOpToString = function() {
	    return "{binop-expr:" + this.type + "," + String(this.left) + "," + String(this.right) + "}";
	};
	
	var getOrdering = function(type) {
	    
	    switch(type) {
	        case xpm.XPathExpressionTypeEnum.OR:
	        case xpm.XPathExpressionTypeEnum.AND:
	            return "right";
	        case xpm.XPathExpressionTypeEnum.EQ:
	        case xpm.XPathExpressionTypeEnum.NEQ:
	        case xpm.XPathExpressionTypeEnum.LT:
	        case xpm.XPathExpressionTypeEnum.LTE:
	        case xpm.XPathExpressionTypeEnum.GT:
	        case xpm.XPathExpressionTypeEnum.GTE:
	        case xpm.XPathExpressionTypeEnum.PLUS:
	        case xpm.XPathExpressionTypeEnum.MINUS:
	        case xpm.XPathExpressionTypeEnum.MULT:
	        case xpm.XPathExpressionTypeEnum.DIV:
	        case xpm.XPathExpressionTypeEnum.MOD:
	        case xpm.XPathExpressionTypeEnum.UNION:
	            return "left";
	        case xpm.XPathExpressionTypeEnum.UMINUS:
	            return "nonassoc";
	        default:
	            throw("No order for " + type);
	    }
	};
	
	var getPrecedence = function(type) {
	    // we need to mimic the structure defined in the jison file
	    //%right OR
	    //%right AND
	    //%left EQ NEQ
	    //%left LT LTE GT GTE
	    //%left PLUS MINUS
	    //%left MULT DIV MOD
	    //%nonassoc UMINUS
	    //%left UNION
	    switch(type) {
	        case xpm.XPathExpressionTypeEnum.OR:
	            return 0;
	        case xpm.XPathExpressionTypeEnum.AND:
	            return 1;
		    case xpm.XPathExpressionTypeEnum.EQ:
		    case xpm.XPathExpressionTypeEnum.NEQ:
		        return 2;
		    case xpm.XPathExpressionTypeEnum.LT:
		    case xpm.XPathExpressionTypeEnum.LTE:
		    case xpm.XPathExpressionTypeEnum.GT:
		    case xpm.XPathExpressionTypeEnum.GTE:
		        return 3;
		    case xpm.XPathExpressionTypeEnum.PLUS:
		    case xpm.XPathExpressionTypeEnum.MINUS:
		        return 4;
		    case xpm.XPathExpressionTypeEnum.MULT:
		    case xpm.XPathExpressionTypeEnum.DIV:
		    case xpm.XPathExpressionTypeEnum.MOD:
		        return 5;
		    case xpm.XPathExpressionTypeEnum.UMINUS:
		        return 6;
		    case xpm.XPathExpressionTypeEnum.UNION:
		        return 7;
	        default:
	            throw("No precedence for " + type);
	    }     
	};
	
	var isOp = xpm.isOp = function(someToken) {
	    /*
	     * Whether something is an operation
	     */
	    // this is probably breaking an abstraction layer.
	    var str = someToken.toString();
	    return str.indexOf("{binop-expr:") === 0 || str.indexOf("{unop-expr:") === 0;
	};
	
	var isLiteral = xpm.isLiteral = function(someToken) {
        return (someToken instanceof xpm.XPathNumericLiteral || 
                someToken instanceof xpm.XPathStringLiteral ||
                someToken instanceof xpm.XPathPathExpr); 
	};
	
	var isSimpleOp = xpm.isSimpleOp = function(someToken) {
	    return isOp(someToken) && isLiteral(someToken.left) && isLiteral(someToken.right);
	};
	
	var binOpToXPath = function() {
	    var prec = getPrecedence(this.type), lprec, rprec, lneedsParens = false, rneedsParens = false,
	        lString, rString;
	    // if the child has higher precedence we can omit parens
	    // if they are the same then we can omit
	    // if they tie, we look to the ordering
	    if (isOp(this.left)) {
	        lprec = getPrecedence(this.left.type);
	        lneedsParens = (lprec > prec) ? false : (lprec !== prec) ? true : (getOrdering(this.type) === "right");
	    } 
	    if (isOp(this.right)) {
	        rprec = getPrecedence(this.right.type);
	        rneedsParens = (rprec > prec) ? false : (rprec !== prec) ? true : (getOrdering(this.type) === "left");
	    } 
	    lString = lneedsParens ? "(" + this.left.toXPath() + ")" : this.left.toXPath();
	    rString = rneedsParens ? "(" + this.right.toXPath() + ")" : this.right.toXPath();
	    return lString + " " + expressionTypeEnumToXPathLiteral(this.type) + " " + rString;
	};
	
	var binOpChildren = function () {
	    return [this.left, this.right];
	};
	
	xpm.XPathBoolExpr = function(definition) {
	    this.type = definition.type;
	    this.left = definition.left;
	    this.right = definition.right;
	    this.toString = binOpToString;
	    this.toXPath = binOpToXPath;
	    this.getChildren = binOpChildren;
	    return this;
        
	};
	
	xpm.XPathEqExpr = function(definition) {
	    this.type = definition.type;
	    this.left = definition.left;
	    this.right = definition.right;
	    this.toString = binOpToString;
	    this.toXPath = binOpToXPath;
	    this.getChildren = binOpChildren;
        return this;
	};
	
	xpm.XPathCmpExpr = function(definition) {
	    this.type = definition.type;
	    this.left = definition.left;
	    this.right = definition.right;
	    this.toString = binOpToString;
	    this.toXPath = binOpToXPath;
	    this.getChildren = binOpChildren;
        return this;
	};
	 
	xpm.XPathArithExpr = function(definition) {
	    this.type = definition.type;
	    this.left = definition.left;
	    this.right = definition.right;
	    this.toString = binOpToString;
	    this.toXPath = binOpToXPath;
	    this.getChildren = binOpChildren;
        return this;
	};
	
	xpm.XPathUnionExpr = function(definition) {
	    this.type = definition.type;
	    this.left = definition.left;
	    this.right = definition.right;
	    this.toString = binOpToString;
	    this.toXPath = binOpToXPath;
	    this.getChildren = binOpChildren;
        return this;
	};
	
	xpm.XPathNumNegExpr = function(definition) {
	    this.type = definition.type;
	    this.value = definition.value;
	    this.toString = function() {
	        return "{unop-expr:" + this.type + "," + String(this.value) + "}";
	    };
	    this.toXPath = function() {
	        return "-" + this.value.toXPath();
	    };
	    this.getChildren = function () {
	       return [this.value];
	    }
        return this;
	};
}());