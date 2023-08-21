hqDefine('app_manager/js/app_manager_utils', [
    'jquery',
    'underscore',
], function (
    $,
    _
) {
    var getBitlyToPhoneticDict = function () {
        var natoPhonetic = {
            "A": "Alpha",
            "B": "Bravo",
            "C": "Charlie",
            "D": "Delta",
            "E": "Echo",
            "F": "Foxtrot",
            "G": "Golf",
            "H": "Hotel",
            "I": "India",
            "J": "Juliett",
            "K": "Kilo",
            "L": "Lima",
            "M": "Mike",
            "N": "November",
            "O": "Oscar",
            "P": "Papa",
            "Q": "Quebec",
            "R": "Romeo",
            "S": "Sierra",
            "T": "Tango",
            "U": "Uniform",
            "V": "Victor",
            "W": "Whiskey",
            "X": "X-ray",
            "Y": "Yankee",
            "Z": "Zulu",
        };
        var bitlyToPhonetic = {
            '0': 'zero',
            '1': 'one',
            '2': 'two',
            '3': 'three',
            '4': 'four',
            '5': 'five',
            '6': 'six',
            '7': 'seven',
            '8': 'eight',
            '9': 'nine',
        };
        bitlyToPhonetic = _(bitlyToPhonetic).extend(_.object(_(natoPhonetic).map(function (v, k) {
            return [k.toLowerCase(), v.toLowerCase()];
        })));
        bitlyToPhonetic = _(bitlyToPhonetic).extend(_.object(_(natoPhonetic).map(function (v, k) {
            return [k.toUpperCase(), v.toUpperCase()];
        })));
        return bitlyToPhonetic;
    };

    var bitlyToPhonetic;
    var bitlyNatoPhonetic = function (bitlyUrl) {
        /**
         * We use this method to explicitly spell out the bitly code for
         * users who have trouble reading the letters (esp. 1 and l, O and 0)
         */
        'use strict';
        if (bitlyToPhonetic === undefined) {
            bitlyToPhonetic = getBitlyToPhoneticDict();
        }
        if (bitlyUrl) {
            var bitlyCode = bitlyUrl.replace('http://bit.ly/', '');
            var phonetics = [];
            for (var i = 0; i < bitlyCode.length; i++) {
                phonetics.push(bitlyToPhonetic[bitlyCode[i]] || 'symbol');
            }
            return phonetics.join(' ');
        }
    };

    var handleAjaxAppChange = function (callback) {
        $(document).ajaxComplete(function (e, xhr, options) {
            xhr.done(() => {
                var match = options.url.match(/\/apps\/(.*)/);
                if (match) {
                    var suffix = match[1];  // first captured group
                    if (/^edit_form_attr/.test(suffix) ||
                        /^edit_module_attr/.test(suffix) ||
                        /^edit_module_detail_screens/.test(suffix) ||
                        /^edit_app_attr/.test(suffix) ||
                        /^edit_form_actions/.test(suffix) ||
                        /^edit_commcare_settings/.test(suffix) ||
                        /^rearrange/.test(suffix) ||
                        /^patch_xform/.test(suffix)) {
                        callback();
                    }
                }
            });
        });
    };

    return {
        bitlyNatoPhonetic: bitlyNatoPhonetic,
        handleAjaxAppChange: handleAjaxAppChange,
    };
});
