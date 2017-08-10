/*
 *  Manage data needed by JavaScript but supplied by server.
 *
 *  In django templates, use {% initial_page_data varName varValue %} to
 *  define data, then in JavaScript use this module's get function to
 *  access it.
 */
hqDefine('hqwebapp/js/initial_page_data.js', function () {
    var selector = ".initial-page-data",
        data = {};

    /*
     * Fetch a named value.
     */
    var get = function(name) {
        if (data[name] === undefined) {
            data = gather(selector, data);
        }
        return data[name];
    };

    /*
     *  Find any unregistered data. Error on any duplicates.
     */
    var gather = function(selector, existing) {
        existing = existing || {};
        $(selector).each(function() {
            _.each($(this).children(), function(div) {
                var $div = $(div),
                    data = $div.data();
                if (existing[data.name] !== undefined) {
                    throw new Error("Duplicate key in initial page data: " + data.name);
                }
                existing[data.name] = data.value;
                $div.remove();
            });
        });
        return existing;
    };

    $(function() {
        data = gather(selector, data);
    });

    return {
        gather: gather,
        get: get,
    };
});
