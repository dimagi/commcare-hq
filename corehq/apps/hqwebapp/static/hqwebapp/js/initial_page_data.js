/*
 *  Manage data needed by JavaScript but supplied by server.
 *
 *  In django templates, use {% initial_page_data varName varValue %} to
 *  define data, then in JavaScript use this module's get function to
 *  access it.
 */
var COMMCAREHQ_INITIAL_PAGE_DATA = {};
hqDefine('hqwebapp/js/initial_page_data.js', function () {
    /*
     * Fetch a named value.
     */
    var get = function(name) {
        if (COMMCAREHQ_INITIAL_PAGE_DATA[name] === undefined) {
            gather();
        }
        return COMMCAREHQ_INITIAL_PAGE_DATA[name];
    };

    /*
     *  Find any unregistered data. Error on any duplicates.
     */
    var gather = function() {
        $(".initial-page-data").each(function() {
            _.each($(this).children(), function(div) {
                var $div = $(div),
                    data = $div.data();
                if (COMMCAREHQ_INITIAL_PAGE_DATA[data.name] !== undefined) {
                    throw new Error("Duplicate key in initial page data: " + data.name);
                }
                var value = data.value;

                // The initial_page_data tag escapes whitespace with \n, etc. for the sake of
                // printing the value in a data attribute. Unescape here.
                if (typeof value === "string") {
                    value = JSON.parse('"' + value + '"');
                }

                COMMCAREHQ_INITIAL_PAGE_DATA[data.name] = value;
                $div.remove();
            });
        });
    };

    $(gather);

    return {
        get: get,
    };
});
