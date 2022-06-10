hqDefine('dhis2/js/json_syntax_parse', [
], function () {
    /*

    This is a rewrite of the core of json-parse-even-better-errors library,
    adapted to suit the needs of DHIS2 config handling.
    Original can be found here: https://github.com/npm/json-parse-even-better-errors/blob/latest/index.js

    */

    var parseError = function (e, txt, context) {
      if (!txt) {
        return {
          message: e.message + ' while parsing empty string',
          position: 0,
        }
      }
      var badToken = e.message.startsWith('Unexpected token') ?
        e.message.match(/^Unexpected token (.|\n) .*position\s+(\d+)/i)
        : e.message.match(/^Unexpected ([^\s]+) .*position\s+(\d+)/i)

      var errIdx = badToken ? +badToken[2]
        : e.message.match(/^Unexpected end of JSON.*/i) ? txt.length - 1
        : null

      var msg = badToken ? e.message.replace(/^Unexpected token ./, `Unexpected token ${
          JSON.stringify(badToken[1])
        }`)
        : e.message
      if (badToken != null && badToken[1] === '\n') {
        msg = msg.replace(/[\n\r]/, 'at end of row')
      }

      // To clean up/refactor later
      // Not sure this is even right
      var helpText = "";
      if (e.message.startsWith('Unexpected token')) {
        if (badToken[1] === '\n') {
            helpText = 'Expected: STRING, NUMBER, NULL, TRUE, FALSE, {, ['
        }
        else {
            helpText = "Expected: }, ',', ]"
        }
      }
      else {
        helpText = "Expected: }, :, ',', ]"
      }

      var errorRow = txt.slice(0, errIdx).split('\n').length - 1
      msg = msg.replace(/position [0-9]*/, `row ${errorRow}`)

      if (errIdx !== null && errIdx !== undefined) {
        var start = errIdx <= context ? 0 : errIdx - context
        var end = errIdx + context >= txt.length ? txt.length : errIdx + context
        var slice = (start === 0 ? '' : '...') +
          txt.slice(start, errIdx) + '{ERROR}' + txt.slice(errIdx, end) +
          (end === txt.length ? '' : '...')

        var near = txt === slice ? '' : 'near '
        return {
          message: msg + ` while parsing ${near}\n${slice}\n` + helpText,
          position: errIdx,
        }
      }
      else {
        return {
          message: msg + ` while parsing '${txt.slice(0, context * 2)}'`,
          position: 0,
        }
      }
    }

    class JSONParseError extends SyntaxError {
      constructor (er, txt, context, caller) {
        context = context || 20
        var metadata = parseError(er, txt, context)
        super(metadata.message)
      }
    }

    var parseJson = function (txt, reviver, context) {
      context = context || 20
      try {
        return JSON.parse(txt, reviver)
      } catch (e) {
        throw new JSONParseError(e, txt, context, parseJson)
      }
    }

    return {
        parseJson: parseJson,
    };
});
