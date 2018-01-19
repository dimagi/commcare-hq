hqDefine('hqwebapp/js/ui-element', [
    'underscore',
    'hqwebapp/js/ui_elements/ui-element-input',
    'hqwebapp/js/ui_elements/ui-element-select',
    'hqwebapp/js/ui_elements/ui-element-key-val-list',
    'hqwebapp/js/ui_elements/ui-element-input-map',
    'hqwebapp/js/ui_elements/ui-element-checkbox',
    'hqwebapp/js/ui_elements/ui-element-langcode-button',
    'hqwebapp/js/ui_elements/ui-element-key-val-mapping',
], function (
    _,
    inputElement,
    selectElement,
    keyValueList,
    inputMap,
    checkboxElement,
    langcodeButton,
    keyValueMapping
) {
    'use strict';
    var module = {};

    module.input = function (value) {
        return inputElement.new(value);
    };

    module.textarea = function () {
        return inputElement.new_textarea();
    };

    module.select = function (options) {
        return selectElement.new(options);
    };

    module.map_list = function(guid, modalTitle) {
        return keyValueList.new(guid, modalTitle);
    };

    module.input_map = function(show_del_button) {
        return inputMap.new(show_del_button);
    };

    module.checkbox = function () {
        return checkboxElement.new();
    };

    module.langcode_tag_btn = function ($elem, new_lang) {
        return langcodeButton.new($elem, new_lang);
    };

    module.key_value_mapping = function (options) {
        return keyValueMapping.new(options);
    };

    module.serialize = function (obj) {
        var cpy;
        if (typeof obj.val === 'function') {
            return obj.val();
        } else if (_.isArray(obj)) {
            return _.map(obj, module.serialize);
        } else if (_.isObject(obj)) {
            cpy = _.clone(obj);
            _.chain(cpy).map(function (value, key) {
                cpy[key] = module.serialize(value);
            });
            return cpy;
        } else {
            return obj;
        }
    };

    return module;

});
