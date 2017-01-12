var COMMCAREHQ_INITIAL_PAGE_DATA = {};
hqDefine('hqwebapp/js/initial_page_data.js', function () {
    var get = function(name) {
        if (COMMCAREHQ_INITIAL_PAGE_DATA[name] === undefined) {
            gather();
        }
        return COMMCAREHQ_INITIAL_PAGE_DATA[name];
    };

    var gather = function() {
        _.each($(".initial-page-data"), function(div) {
            var $div = $(div),
                data = $div.data();
            if (COMMCAREHQ_INITIAL_PAGE_DATA[data.name] !== undefined) {
                throw new Error("Duplicate key in initial page data: " + data.name);
            }
            COMMCAREHQ_INITIAL_PAGE_DATA[data.name] = data.value;
            $div.remove();
        });
    };

    $(gather);

    return {
        get: get,
    };
});
