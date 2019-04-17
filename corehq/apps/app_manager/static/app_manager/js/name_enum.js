hqDefine("app_manager/js/name_enum", function () {
    var init = function (options) {
        hqImport("hqwebapp/js/assert_properties").assertRequired(options, ['items', 'lang', 'langs', 'name', 'selector']);

        $nameEnumContainer = $(options.selector);
        if ($nameEnumContainer.length) {
            var nameMapping = hqImport('hqwebapp/js/ui-element').key_value_mapping({
                lang: options.lang,
                langs: options.langs,
                items: options.items,
                property_name: 'name',
                values_are_icons: false,
                keys_are_conditions: true,
            });
            nameMapping.on("change", function () {
                $nameEnumContainer.find("[name='" + options.name + "']").val(JSON.stringify(this.getItems()));
                $nameEnumContainer.find("[name='" + options.name + "']").trigger('change');    // trigger save button
            });
            $nameEnumContainer.append(nameMapping.ui);
        }
    };

    return {
        init: init,
    };
});
