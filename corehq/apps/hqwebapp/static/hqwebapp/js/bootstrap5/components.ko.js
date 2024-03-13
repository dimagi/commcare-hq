hqDefine("hqwebapp/js/bootstrap5/components.ko", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/components/inline_edit',
    'hqwebapp/js/components/pagination',
    'hqwebapp/js/components/search_box',
    'hqwebapp/js/components/select_toggle',
    'hqwebapp/js/components/bootstrap5/feedback',
], function (
    $,
    ko,
    _,
    inlineEdit,
    pagination,
    searchBox,
    selectToggle,
    feedback
) {
    var components = {
        'inline-edit': inlineEdit,
        'pagination': pagination,
        'search-box': searchBox,
        'select-toggle': selectToggle,
        'feedback': feedback,
    };

    _.each(components, function (moduleName, elementName) {
        ko.components.register(elementName, moduleName);
    });

    $(function () {
        _.each(_.keys(components), function (elementName) {
            _.each($(elementName), function (el) {
                var $el = $(el);
                if (!($el.data('apply-bindings') === false)) {
                    $(el).koApplyBindings();
                }
            });
        });
    });

    return 1;
});
