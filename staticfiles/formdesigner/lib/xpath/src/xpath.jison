
/* DON'T EDIT THIS FILE UNLESS YOU KNOW WHAT YOU'RE DOING */

/* This jison grammar file is based off of the javarosa grammar file which can be found here:
 * https://bitbucket.org/javarosa/javarosa/src/tip/core/src/org/javarosa/xpath/parser/xpath.grammar
 *
 * Also see the associated lex file:
 * https://bitbucket.org/javarosa/javarosa/src/tip/core/src/org/javarosa/xpath/parser/xpath.flex
 *
 * To build run:
 *   $ ./bin/jison xpath.jison xpath.jisonlex
 */



/* 
 *  TODO Code?
 */

%right OR
%right AND
%left EQ NEQ
%left LT LTE GT GTE
%left PLUS MINUS
%left MULT DIV MOD
%nonassoc UMINUS
%left UNION

%%

xpath_expr:  expr EOF   { return $1; }
    ;

 
expr:   base_expr                   {  $$ = $1; } /* not necessary as this is the default */
    |   op_expr                     {  $$ = $1; }
    |   path_expr                   {  $$ = $1; }
    ;

base_expr:  LPAREN expr RPAREN            { $$ = $2; }
        |   func_call                
        |   VAR                           { $$ = new xpathmodels.XPathVariableReference($1); }
        |   literal               
        ;

op_expr: expr OR expr               { $$ = new xpathmodels.XPathBoolExpr({"type": "or", "left": $1, "right": $3}); }
    |   expr AND expr               { $$ = new xpathmodels.XPathBoolExpr({"type": "and", "left": $1, "right": $3}); }
    |   expr EQ expr                { $$ = new xpathmodels.XPathEqExpr({"type": "==", "left": $1, "right": $3}); }
    |   expr NEQ expr               { $$ = new xpathmodels.XPathEqExpr({"type": "!=", "left": $1, "right": $3}); }
    |   expr LT expr                { $$ = new xpathmodels.XPathCmpExpr({"type": "<", "left":$1, "right": $3}); }
    |   expr LTE expr               { $$ = new xpathmodels.XPathCmpExpr({"type": "<=", "left":$1, "right": $3}); }
    |   expr GT expr                { $$ = new xpathmodels.XPathCmpExpr({"type": ">", "left":$1, "right": $3}); }
    |   expr GTE expr               { $$ = new xpathmodels.XPathCmpExpr({"type": ">=", "left":$1, "right": $3}); }
    |   expr PLUS expr              { $$ = new xpathmodels.XPathArithExpr({"type": "+", "left":$1, "right": $3}); }
    |   expr MINUS expr             { $$ = new xpathmodels.XPathArithExpr({"type": "-", "left":$1, "right": $3}); }
    |   expr MULT expr              { $$ = new xpathmodels.XPathArithExpr({"type": "*", "left":$1, "right": $3}); }
    |   expr DIV expr               { $$ = new xpathmodels.XPathArithExpr({"type": "/", "left":$1, "right": $3}); }
    |   expr MOD expr               { $$ = new xpathmodels.XPathArithExpr({"type": "%", "left":$1, "right": $3}); }
    |   MINUS expr %prec UMINUS     { $$ = new xpathmodels.XPathNumNegExpr({"type": "num-neg", "value":$2}); }
    |   expr UNION expr             { $$ = new xpathmodels.XPathUnionExpr({"type": "union", "left":$1, "right": $3}); } 
    ;

func_call:  QNAME LPAREN arg_list RPAREN   { $$ = new xpathmodels.XPathFuncExpr({id: $1, args: $3}); } 
        |   QNAME LPAREN RPAREN            { $$ = new xpathmodels.XPathFuncExpr({id: $1, args: []}); } 
        ;

arg_list:   arg_list COMMA expr     { var args = $1;
                                      args.push($3);
                                      $$ = args; }         
        |   expr                    { $$ = [$1]; }
        ;

path_expr:  loc_path
        ; 

/* This is commented out because there might be a bug in jison that thinks this is ambiguous
 * when in fact it's not. The first group belongs as part of the path_expr. The second should
 * be added as a new filter_expr.
 */

/*
        |   filter_expr SLASH rel_loc_path          { $$ = "fe.unwrapPathExpr(rlp)"; }
        |   filter_expr DBL_SLASH rel_loc_path      { $$ = "fe.unwrapPathExpr(Vprepend(rlp, xpathmodels.XPathStep.ABBR_DESCENDANTS()))"; }
        ;

filter_expr:  filter_expr predicate     { $$ = "Vappend(fe.v, p); RESULT = fe;" }
|   base_expr                   { $$ = "new vectorWrapper(be);"; } ***** THIS IS THE LINE THAT BREAKS *****  
        ;
*/ 

predicate:   LBRACK expr RBRACK            { $$ = $2; }
        ;


loc_path:   rel_loc_path                    { $$ = new xpathmodels.XPathPathExpr({initial_context: xpathmodels.XPathInitialContextEnum.RELATIVE,
                                                                      steps: $1}); }
        |   SLASH rel_loc_path              { $$ = new xpathmodels.XPathPathExpr({initial_context: xpathmodels.XPathInitialContextEnum.ROOT,
                                                                      steps: $2}); }
        |   DBL_SLASH rel_loc_path          { var steps = $2;
                                              // insert descendant step into beginning
                                              steps.splice(0, 0, new xpathmodels.XPathStep({axis: xpathmodels.XPathAxisEnum.DESCENDANT_OR_SELF, 
                                                                                test: xpathmodels.XPathTestEnum.TYPE_NODE}));
                                              $$ = new xpathmodels.XPathPathExpr({initial_context: xpathmodels.XPathInitialContextEnum.ROOT,
                                                                      steps: steps}); }
        |   SLASH                   { $$ = new xpathmodels.XPathPathExpr({initial_context: xpathmodels.XPathInitialContextEnum.ROOT,
                                                              steps: []});}
        ;

rel_loc_path: step                        { $$ = [$1];}
        |   rel_loc_path SLASH step       { var path = $1;
                                            path.push($3);
                                            $$ = path; }
        |   rel_loc_path DBL_SLASH step   { var path = $1;
                                            path.push(new xpathmodels.XPathStep({axis: xpathmodels.XPathAxisEnum.DESCENDANT_OR_SELF, 
                                                                     test: xpathmodels.XPathTestEnum.TYPE_NODE}));
                                            path.push($3);
                                            $$ = path; }
        ;

step:   step_unabbr                 { $$ = $1; }
    |   DOT                         { $$ = new xpathmodels.XPathStep({axis: xpathmodels.XPathAxisEnum.SELF, 
                                                          test: xpathmodels.XPathTestEnum.TYPE_NODE}); }
    |   DBL_DOT                     { $$ = new xpathmodels.XPathStep({axis: xpathmodels.XPathAxisEnum.PARENT, 
                                                          test: xpathmodels.XPathTestEnum.TYPE_NODE}); }
    ;

step_unabbr:  step_unabbr predicate       { var step = $1;
                                            step.predicates.push($2);
                                            $$ = step; }
        |   step_body                { $$ = $1; }
        ;

step_body: node_test                    { var nodeTest = $1; // temporary dict with appropriate args
                                          nodeTest.axis = xpathmodels.XPathAxisEnum.CHILD;
                                          $$ = new xpathmodels.XPathStep(nodeTest); }
        |   axis_specifier node_test    { var nodeTest = $2;  // temporary dict with appropriate args
                                          nodeTest.axis = $1; // add axis
                                          $$ = new xpathmodels.XPathStep(nodeTest); }
        ;

axis_specifier:  QNAME DBL_COLON           { $$ = xpathmodels.validateAxisName($1); }
        |   AT                  { $$ = xpathmodels.XPathAxisEnum.ATTRIBUTE; }
        ;

node_test:  QNAME                 { $$ = {"test": xpathmodels.XPathTestEnum.NAME, "name": $1}; }
        |   WILDCARD                { $$ = {"test": xpathmodels.XPathTestEnum.NAME_WILDCARD}; }
        |   NSWILDCARD              { $$ = {"test": xpathmodels.XPathTestEnum.NAMESPACE_WILDCARD, "namespace": $1}; }
        |   NODETYPE_NODE LPAREN RPAREN     { $$ = {"test": xpathmodels.XPathTestEnum.TYPE_NODE}; }
        |   NODETYPE_TEXT LPAREN RPAREN     { $$ = {"test": xpathmodels.XPathTestEnum.TYPE_TEXT}; }
        |   NODETYPE_COMMENT LPAREN RPAREN      { $$ = {"test": xpathmodels.XPathTestEnum.TYPE_COMMENT}; }
        |   NODETYPE_PROCINSTR LPAREN RPAREN  { $$ = {"test": xpathmodels.XPathTestEnum.TYPE_PROCESSING_INSTRUCTION, "literal": null}; }
        |   NODETYPE_PROCINSTR LPAREN STR RPAREN  { $$ = {"test": xpathmodels.XPathTestEnum.TYPE_PROCESSING_INSTRUCTION, "literal": $3}; }
        ;

literal: STR                       { $$ = new xpathmodels.XPathStringLiteral($1); }
    |   NUM                       { $$ = new xpathmodels.XPathNumericLiteral($1); }
    ;
  