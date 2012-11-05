// http://stackoverflow.com/a/3561711
RegExp.escape = function(s) {
    return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
};

$.fn.multiTypeahead = function (options) {
    /**
     * An extension of the Bootstrap typeahead jQuery plugin that handles
     * creating a comma-separated list and prevents duplicate values.
     *
     * @author mwhite
     */

    function current_val_and_input(string) {
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
        matcher: function(item) {
            var split = current_val_and_input(this.$element.val()),
                current_val = split[0],
                current_input = split[1];

            var pattern = new RegExp("(?:^|,\\s*)" + RegExp.escape(item) + "(?:\\s*,?|$)");
            if (current_val.match(pattern)) {
                return 0;
            }
            return ~item.toLowerCase().indexOf(current_input.toLowerCase());
        },
        updater: function (item) {
            var split = current_val_and_input(this.$element.val()),
                current_val = split[0];

            this.$element.focus();
            return current_val + item + ', ';
        }
    });

    return this.each(function (i, v) {
        $(v).typeahead(options);
    });
};
