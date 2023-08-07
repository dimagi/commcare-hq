hqDefine('generic_inbound/js/manage_links', [
    "hqwebapp/js/initial_page_data",
], function (initialPageData) {
    // manages the expression links in the API form

    const getExpressionUrl = function (expressionId) {
        if (expressionId) {
            return initialPageData.reverse('edit_ucr_expression', expressionId);
        } else {
            return initialPageData.reverse('ucr_expressions');
        }
    };

    $(function () {
        // update the links based on selection
        const filterLinkEl = $('#div_id_filter_expression .input-group-addon a');
        const transformLinkEl = $('#div_id_transform_expression .input-group-addon a');
        const filterSelect = $('#id_filter_expression');
        const transformSelect = $('#id_transform_expression');

        const updateLink = function (selectEl, element) {
            let optionSelected = selectEl.find("option:selected");
            element.attr('href', getExpressionUrl(optionSelected.val()));
        };

        filterSelect.change(function () {
            updateLink($(this), filterLinkEl);
        });

        transformSelect.change(function () {
            updateLink($(this), transformLinkEl);
        });

        // update based on initial values
        updateLink(filterSelect, filterLinkEl);
        updateLink(transformSelect, transformLinkEl);
    });

    return {
        getExpressionUrl: getExpressionUrl,
    };
});
