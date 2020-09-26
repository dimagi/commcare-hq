hqDefine('hqwebapp/js/ui_elements/ui-element-langcode-button', [
    'jquery',
], function (
    $
) {
    'use strict';
    var module = {};

    var LangCodeButton = function ($elem, new_lang) {
        this.button = $elem;
        this.button.click(function () {
            return false;
        });
        this.lang_code = new_lang;
        this.lang(new_lang);
    };
    LangCodeButton.prototype = {
        lang: function (value) {
            if (value === undefined) {
                return this.lang_code;
            } else {
                this.lang_code = value;
                this.button.text(this.lang_code);
            }
        },
    };

    module.translate_delim = function (value) {
        var values = value.split(module.LANG_DELIN);
        return {
            value: values[0],
            lang: (values.length > 1 ? values[1] : null),
        };
    };

    module.LANG_DELIN = "{{[[*LANG*]]}}";

    module.new = function ($elem, new_lang) {
        return new LangCodeButton($elem, new_lang);
    };

    return module;

});
