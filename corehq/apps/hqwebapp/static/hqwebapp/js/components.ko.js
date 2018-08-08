hqDefine("hqwebapp/js/components.ko", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/components/inline_edit',
], function(
    $,
    ko,
    _,
    inlineEdit
) {
    var components = {
        'inline-edit': inlineEdit,
    };

    _.each(components, function(moduleName, elementName) {
        ko.components.register(elementName, moduleName);
    });

    $(function() {
        _.each(_.keys(components), function(elementName) {
            _.each($(elementName), function(el) {
                var $el = $(el);
                if (!$el.closest('.ko-template').length) {
                    $(el).koApplyBindings();
                }
            });
        });
    });
});
