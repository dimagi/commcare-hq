var choiceListUtils = (function() {
    var module = {};
    // todo: we may need to support configuring this in the future
    var pageSize = 20;

    module.getApiQueryParams = function (term, page) {
        return {
            q: term, // search term
            page: page,
            limit: pageSize
        };
    };
    module.formatValueForSelect2 = function (val) {
        return {'id': val.value, 'text': val.display || ''};
    };
    module.formatPageForSelect2 = function (data, page) {
        // parse the results into the format expected by Select2.
        var formattedData = _.map(data, module.formatValueForSelect2);
        return {
            results: formattedData,
            more: data.length === pageSize
        };
    };
    return module;
})();
