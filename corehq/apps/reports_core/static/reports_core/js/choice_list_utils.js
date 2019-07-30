hqDefine('reports_core/js/choice_list_utils', ['underscore'], function (_) {
    var module = {};
    var pageSize = 20;

    module.getApiQueryParams = function (params) {
        return {
            q: params.term, // search term
            page: params.page,
            limit: pageSize,
        };
    };
    module.formatValueForSelect2 = function (val) {
        return {'id': val.value, 'text': val.display || ''};
    };
    module.formatPageForSelect2 = function (data) {
        // parse the results into the format expected by Select2.
        var formattedData = _.map(data, module.formatValueForSelect2);
        return {
            results: formattedData,
            more: data.length === pageSize,
        };
    };
    return module;
});
