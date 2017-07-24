/* globals hqImport, hqDefine */

hqDefine('style/js/ui-element.js', function () {
    'use strict';
    var module = {};

    module.input = function (value) {
        return hqImport('style/js/ui_elements/ui-element-input.js').new(value);
    };

    module.textarea = function () {
        return hqImport('style/js/ui_elements/ui-element-input.js').new_textarea();
    };

    module.select = function (options) {
        return hqImport('style/js/ui_elements/ui-element-select.js').new(options);
    };

    module.map_list = function(guid, modalTitle) {
        return hqImport('style/js/ui_elements/ui-element-key-val-list.js').new(guid, modalTitle);
    };

    module.input_map = function(show_del_button) {
        return hqImport('style/js/ui_elements/ui-element-input-map.js').new(show_del_button);
    };

    module.checkbox = function () {
        return hqImport('style/js/ui_elements/ui-element-checkbox.js').new();
    };

    module.langcode_tag_btn = function ($elem, new_lang) {
        return hqImport('style/js/ui_elements/ui-element-langcode-button.js').new($elem, new_lang);
    };

    module.key_value_mapping = function (options) {
        return hqImport('style/js/ui_elements/ui-element-key-val-mapping.js').new(options);
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
