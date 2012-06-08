WhiteSpace          (\s+)
Digit               [0-9]
Letter              [A-Za-z]
NameStartChar       [A-Za-z_]
NameTrailChar       [A-Za-z0-9._-]
NCName              [A-Za-z_][A-Za-z0-9._-]*
QName               [A-Za-z_][A-Za-z0-9._-]*(":"[A-Za-z_][A-Za-z0-9._-]*)?

%s INITIAL OP_CONTEXT VAL_CONTEXT
      
%%

<*>{WhiteSpace}                         /* ignore whitespace */ 

<*>"node"/({WhiteSpace}?"(")                     { debuglog("NODETYPE", yytext); return "NODETYPE_NODE"; }
<*>"text"/({WhiteSpace}?"(")                     { debuglog("NODETYPE", yytext); return "NODETYPE_TEXT"; }

<*>"comment"/({WhiteSpace}?"(")                  { debuglog("NODETYPE", yytext); return "NODETYPE_COMMENT"; }
<*>"processing-instruction"/({WhiteSpace}?"(")   { debuglog("NODETYPE", yytext); return "NODETYPE_PROCINSTR"; }

<*>"$"{QName}                                      { this.begin("OP_CONTEXT"); yytext = yytext.substr(1,yyleng-1); debuglog("VAR", yytext); return "VAR"; }

<VAL_CONTEXT,INITIAL>{NCName}":*"  { this.begin("OP_CONTEXT"); 
                                     yytext = yytext.substr(0, yyleng-2);
                                     debuglog("NSWILDCARD", yytext); return "NSWILDCARD"; }
<VAL_CONTEXT,INITIAL>{QName}       { this.begin("OP_CONTEXT"); debuglog("QNAME", yytext); return "QNAME"; } 
<VAL_CONTEXT,INITIAL>"*"           { this.begin("OP_CONTEXT"); debuglog("WILDCARD", yytext); return "WILDCARD"; }

<OP_CONTEXT>"*"                    { this.begin("VAL_CONTEXT"); debuglog("MULT", yytext); return "MULT"; }
<OP_CONTEXT>("and")                  { this.begin("VAL_CONTEXT"); debuglog("AND", yytext); return "AND"; }
<OP_CONTEXT>("or")                   { this.begin("VAL_CONTEXT"); debuglog("OR", yytext); return "OR"; }
<OP_CONTEXT>("div")                  { this.begin("VAL_CONTEXT"); debuglog("DIV", yytext); return "DIV"; }
<OP_CONTEXT>("mod")                  { this.begin("VAL_CONTEXT"); debuglog("MOD", yytext); return "MOD"; }

<*>({Digit}+("."{Digit}*)?|("."{Digit}+))             { this.begin("OP_CONTEXT"); debuglog("NUM", yytext); return "NUM"; }


<*>"="         { this.begin("VAL_CONTEXT"); debuglog("EQ", yytext); return "EQ"; }
<*>"!="        { this.begin("VAL_CONTEXT"); debuglog("NEQ", yytext); return "NEQ"; }
<*>"<="        { this.begin("VAL_CONTEXT"); debuglog("LTE", yytext); return "LTE"; }
<*>"<"         { this.begin("VAL_CONTEXT"); debuglog("LT", yytext); return "LT"; }
<*>">="        { this.begin("VAL_CONTEXT"); debuglog("GTE", yytext); return "GTE"; }
<*>">"         { this.begin("VAL_CONTEXT"); debuglog("GT", yytext); return "GT"; }
<*>"+"         { this.begin("VAL_CONTEXT"); debuglog("PLUS", yytext); return "PLUS"; }
<*>"-"         { this.begin("VAL_CONTEXT"); debuglog("MINUS", yytext); return "MINUS"; }
<*>"|"         { this.begin("VAL_CONTEXT"); debuglog("UNION", yytext); return "UNION"; }
<*>"//"        { this.begin("VAL_CONTEXT"); debuglog("DBL", yytext); return "DBL_SLASH"; }
<*>"/"         { this.begin("VAL_CONTEXT"); debuglog("SLASH", yytext); return "SLASH"; }
<*>"["         { this.begin("VAL_CONTEXT"); debuglog("LBRACK", yytext); return "LBRACK"; }
<*>"]"         { this.begin("OP_CONTEXT");  debuglog("RBRACK", yytext); return "RBRACK"; }
<*>"("         { this.begin("VAL_CONTEXT"); debuglog("LPAREN", yytext); return "LPAREN"; }
<*>")"         { this.begin("OP_CONTEXT");  debuglog("RPAREN", yytext); return "RPAREN"; }
<*>".."        { this.begin("OP_CONTEXT");  debuglog("DBL", yytext); return "DBL_DOT"; }
<*>"."         { this.begin("OP_CONTEXT");  debuglog("DOT", yytext); return "DOT"; }
<*>"@"         { this.begin("VAL_CONTEXT"); debuglog("AT", yytext); return "AT"; }
<*>"::"        { this.begin("VAL_CONTEXT"); debuglog("DBL", yytext); return "DBL_COLON"; }
<*>","         { this.begin("VAL_CONTEXT"); debuglog("COMMA", yytext); return "COMMA"; }


<*>("\""[^"\""]*"\""|'\''[^'\'']*'\'')               { this.begin("OP_CONTEXT"); yytext = yytext.substr(1,yyleng-2); debuglog("STR", yytext); return "STR"; }


<*><<EOF>>                              return 'EOF';




