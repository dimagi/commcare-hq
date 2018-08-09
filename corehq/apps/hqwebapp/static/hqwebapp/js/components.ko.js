(function () {
    // standalone components will have their own knockout bindings. Use
    // standalone: false if you want to mix the component into another model
    var components = {
        'inline-edit': {path: 'hqwebapp/js/components/inline_edit', standalone: true},
        'pagination': {path: 'hqwebapp/js/components/pagination', standalone: false},
    };

    _.each(components, function(module, elementName) {
        ko.components.register(elementName, hqImport(module.path));
    });

    $(function() {
        _.each(components, function(module, elementName) {
            if (module.standalone){
                _.each($(elementName), function(el) {
                    var $el = $(el);
                    if (!$el.closest('.ko-template').length) {
                        $(el).koApplyBindings();
                    }
                });
            }
        });
    });
}());
