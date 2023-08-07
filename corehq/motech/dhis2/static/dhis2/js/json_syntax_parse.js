hqDefine('dhis2/js/json_syntax_parse', [
], function () {
    /*

    This is a rewrite of the core of json-parse-even-better-errors library,
    adapted to suit the needs of DHIS2 config handling.
    Original can be found here: https://github.com/npm/json-parse-even-better-errors/blob/latest/index.js

    */

    var parseError = function (error, text, context, editor) {
        if (!text) {
            return {
                message: error.message + ' while parsing empty string',
                position: 0,
            };
        }
        var badToken = error.message.startsWith('Unexpected token') ?
            error.message.match(/^Unexpected token (.|\n) .*position\s+(\d+)/i) :
            error.message.match(/^Unexpected ([^\s]+) .*position\s+(\d+)/i);

        var tokenIndex = 1;
        var positionIndex = 2;

        var errorIndex;
        if (badToken) {
            errorIndex = +badToken[positionIndex];
        } else if (error.message.match(/^Unexpected end of JSON.*/i)) {
            errorIndex = text.length - 1;
        } else {
            errorIndex = null;
        }

        var errorMsg;
        if (badToken) {
            errorMsg = error.message.replace(/^Unexpected token ./,
                `Unexpected token ${JSON.stringify(badToken[tokenIndex])}`);
            if (badToken[tokenIndex] === '\n') {
                errorMsg = errorMsg.replace(/[\n\r]/, 'at end of row');
            }
        } else {
            errorMsg = error.message;
        }

        var helpText;
        if (error.message.startsWith('Unexpected token')) {
            var badChar = badToken[tokenIndex];
            if (badChar === '\n' || badChar === '}' || badChar === ']') {
                helpText = 'Expected: STRING, NUMBER, NULL, TRUE, FALSE, {, [';
            } else {
                helpText = "Expected: }, ',', ]";
            }
            if (badChar === '{' || badChar === '[') {
                helpText = helpText + ", :";
            }
        } else {
            helpText = "Expected: }, :, ',', ]";
        }

        var errorRow = text.slice(0, errorIndex).split('\n').length - 1;
        if (editor > -1) {
            var editorNum = `, Case config ${editor + 1},`;
            errorMsg = errorMsg.replace(/position [0-9]*/, `row ${errorRow}${editorNum}`);
        } else {
            errorMsg = errorMsg.replace(/position [0-9]*/, `row ${errorRow}`);
        }

        if (errorIndex !== null && errorIndex !== undefined) {
            var start = errorIndex <= context ? 0 : errorIndex - context;
            var end = errorIndex + context >= text.length ? text.length : errorIndex + context;
            var slice = (start === 0 ? '' : '...') +
                text.slice(start, errorIndex) + '{ERROR}' + text.slice(errorIndex, end) +
                (end === text.length ? '' : '...');

            var near = text === slice ? '' : 'near ';
            return {
                message: errorMsg + ` while parsing ${near}\n${slice}\n` + helpText,
                position: errorIndex,
            };
        } else {
            return {
                message: errorMsg + ` while parsing '${text.slice(0, context * 2)}'`,
                position: 0,
            };
        }
    };

    class JSONParseError extends SyntaxError {
        constructor(error, text, context, caller, editor) {
            var metadata = parseError(error, text, context, editor);
            super(metadata.message);
        }
    }

    var parseJson = function (text, reviver, context, editor = -1) {
        context = context || 20;
        try {
            return JSON.parse(text, reviver);
        } catch (error) {
            throw new JSONParseError(error, text, context, parseJson, editor);
        }
    };

    return {
        parseJson: parseJson,
    };
});
