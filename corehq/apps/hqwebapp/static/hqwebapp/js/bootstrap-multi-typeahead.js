hqDefine("hqwebapp/js/bootstrap-multi-typeahead",[
    "jquery",
    "bootstrap3-typeahead/bootstrap3-typeahead.min",
],function ($) {
    "use strict";
    // http://stackoverflow.com/a/3561711
    var regExpEscape = function (s) {
        return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
    };

    $.fn.multiTypeahead = function (options) {
        /**
         * An extension of the Bootstrap typeahead jQuery plugin that handles
         * creating a comma-separated list and prevents duplicate values.
         *
         * @author mwhite
         */

        function currentValAndInput(string) {
        /* split the current value and the current input (the latter to be
           matched against.) Handles when users manually edit the input such
           that the number of spaces after a comma is not 1 */
            var index = string.lastIndexOf(',');
            if (index === -1) {
                return ['', ''];
            } else {
                index++;
                while (string.charAt(index) === ' ') {
                    index++;
                }
                return [string.substring(0, index), string.substring(index)];
            }
        }

        options = $.extend(options, {
            matcher: function (item) {
                var split = currentValAndInput(this.$element.val()),
                    currentVal = split[0],
                    currentInput = split[1];

                var pattern = new RegExp("(?:^|,\\s*)" + regExpEscape(item) + "(?:\\s*,?|$)");
                if (currentVal.match(pattern)) {
                    return 0;
                }

                return ~item.toLowerCase().indexOf(currentInput.toLowerCase());
            },
            updater: function (item) {
                var split = currentValAndInput(this.$element.val()),
                    currentVal = split[0];

                this.$element.focus();
                return currentVal + item + ', ';
            },
        });

        return this.each(function (i, v) {
            $(v).typeahead(options);
        });
    };


});
