hqDefine("hqwebapp/js/lib/compression", function() {
    // http://rosettacode.org/wiki/LZW_compression#JavaScript
    var LZW = {
        compress: function (uncompressed) {
            "use strict";
            // Build the dictionary.
            var i,
                dictionary = {},
                c,
                wc,
                w = "",
                result = [],
                dictSize = 0x10000;
            for (i = 0; i < dictSize; i += 1) {
                dictionary[String.fromCharCode(i)] = i;
            }

            for (i = 0; i < uncompressed.length; i += 1) {
                c = uncompressed.charAt(i);
                wc = w + c;
                //Do not use dictionary[wc] because javascript arrays
                //will return values for array['pop'], array['push'] etc
               // if (dictionary[wc]) {
                if (dictionary.hasOwnProperty(wc)) {
                    w = wc;
                } else {
                    result.push(dictionary[w]);
                    // Add wc to the dictionary.
                    dictionary[wc] = dictSize++;
                    w = String(c);
                }
            }

            // Output the code for w.
            if (w !== "") {
                result.push(dictionary[w]);
            }
            return result;
        }
    };

    return {
        LZW: LZW,
    };
});
