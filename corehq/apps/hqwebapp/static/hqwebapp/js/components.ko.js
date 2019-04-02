hqDefine("hqwebapp/js/components.ko", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/components/inline_edit',
    'hqwebapp/js/components/pagination',
    'hqwebapp/js/components/search_box',
    'hqwebapp/js/components/select_toggle',
], function (
    $,
    ko,
    _,
    inlineEdit,
    pagination,
    searchBox,
    selectToggle
) {
    var components = {
        'inline-edit': inlineEdit,
        'pagination': pagination,
        'search-box': searchBox,
        'select-toggle': selectToggle,
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
});
