var app_manager_utils = {};

app_manager_utils.get_bitly_to_phonetic_dict = function () {
    var nato_phonetic = {
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
        "Z": "Zulu"
    };
    var bitly_to_phonetic = {
        '0': 'zero',
        '1': 'one',
        '2': 'two',
        '3': 'three',
        '4': 'four',
        '5': 'five',
        '6': 'six',
        '7': 'seven',
        '8': 'eight',
        '9': 'nine'
    };
    bitly_to_phonetic = _(bitly_to_phonetic).extend(_.object(_(nato_phonetic).map(function (v, k) {
        return [k.toLowerCase(), v.toLowerCase()];
    })));
    bitly_to_phonetic = _(bitly_to_phonetic).extend(_.object(_(nato_phonetic).map(function (v, k) {
        return [k.toUpperCase(), v.toUpperCase()];
    })));
    return bitly_to_phonetic;
};

app_manager_utils.bitly_nato_phonetic = function (bitly_url) {
    /**
     * We use this method to explicitly spell out the bitly code for
     * users with extra special needs.
     */
    'use strict';
    if (app_manager_utils.bitly_to_phonetic === undefined) {
        app_manager_utils.bitly_to_phonetic = app_manager_utils.get_bitly_to_phonetic_dict();
    }
    var bitly_code = bitly_url.replace('http://bit.ly/', '');
    var phonetics = [];
    for (var i = 0; i < bitly_code.length; i++) {
        phonetics.push(app_manager_utils.bitly_to_phonetic[bitly_code[i]] || 'symbol');
    }
    return phonetics.join(' ');
};
