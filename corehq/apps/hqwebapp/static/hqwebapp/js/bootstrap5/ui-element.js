/* globals hqImport, hqDefine */

hqDefine('hqwebapp/js/bootstrap5/ui-element', function () {
    'use strict';
    var module = {};

    module.input = function (value) {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-input').new(value);
    };

    module.textarea = function () {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-input').new_textarea();
    };

    module.select = function (options) {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-select').new(options);
    };

    module.map_list = function (guid, modalTitle) {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-key-val-list').new(guid, modalTitle);
    };

    module.input_map = function (show_del_button) {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-input-map').new(show_del_button);
    };

    module.checkbox = function () {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-checkbox').new();
    };

    module.langcode_tag_btn = function ($elem, new_lang) {
        return hqImport('hqwebapp/js/ui_elements/ui-element-langcode-button').new($elem, new_lang);
    };

    module.key_value_mapping = function (options) {
        return hqImport('hqwebapp/js/ui_elements/bootstrap5/ui-element-key-val-mapping').new(options);
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
