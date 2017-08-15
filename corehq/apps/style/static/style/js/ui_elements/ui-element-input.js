/* globals hqDefine, $, eventize, hqImport */

hqDefine('style/js/ui_elements/ui-element-input', function () {
    'use strict';
    var module = {};

    var Input = function ($elem, initialValue, getElemValue, setElemValue, setPlaceholderValue) {
        var that = this;
        eventize(this);
        this.ui = $('<div class="app-designer-input"/>');
        this.value = "";
        this.edit = true;
        this.getElemValue = function () {
            return getElemValue($elem);
        };
        this.setElemValue = function (value) {
            setElemValue($elem, value);
        };
        this.setPlaceholderValue = function (value) {
            setPlaceholderValue($elem, value);
        };

        this.$edit_view = $elem.on('change textchange', function () {
            that.fire('change');
        });
        this.$noedit_view = $('<span class="ui-element-input"/>');

        this.on('change', function () {
            this.value = this.getElemValue();
            this.$noedit_view.text(this.value);
        });
        this.setEdit(this.edit);
        this.val(initialValue);

        // Trigger the textchange plugin's logic, so that it gets the correct initialValue set
        $elem.trigger('keyup');
    };

    Input.prototype = {
        val: function (value) {
            if (value === undefined) {
                return this.value;
            } else {
                this.value = value;
                this.setVisibleValue(this.value);
                return this;
            }
        },
        setVisibleValue: function (value) {
            var translated = hqImport('style/js/ui_elements/ui-element-langcode-button').translate_delim(value);
            this.ui.find('.lang-text').remove();
            if (translated.lang) {
                this.ui.css("position", "relative");
                var langcode_button = hqImport('style/js/ui_elements/ui-element-langcode-button').new(
                    $('<a href="#" class="btn btn-info btn-xs lang-text" style="position: absolute; top: 6px; right: 6px;" />'),
                    translated.lang
                );
                this.ui.append(langcode_button.button);
                this.setPlaceholderValue(translated.value);
                this.$edit_view.change(function () {
                    if ($(this).val() === "")
                        langcode_button.button.show();
                    else
                        langcode_button.button.hide();
                });
            } else
                this.setElemValue(translated.value);
            this.$noedit_view.text(translated.value);
            this.setIcon(this.icon);
            return this;
        },
        setHtml: function (value) {
            this.$noedit_view.html(value);
            this.setIcon(this.icon);
            return this;
        },
        setIcon: function (icon) {
            this.icon = icon;
            if (icon) {
                $('<i> </i>').addClass(icon).prependTo(this.$noedit_view);
            }
            return this;
        },
        setEdit: function (edit) {
            this.edit = edit;
            this.$edit_view.detach();
            this.$noedit_view.detach();
            if (this.edit) {
                this.$edit_view.prependTo(this.ui);
            } else {
                this.$noedit_view.prependTo(this.ui);
            }
            return this;
        },
    };

    module.new = function (value) {
        return new Input($('<input type="text" class="form-control"/>'), value, function ($elem) {
            return $elem.val();
        }, function ($elem, value) {
            return $elem.val(value);
        }, function ($elem, value){
            return $elem.attr('placeholder', value);
        });
    };

    module.new_textarea = function () {
        return new Input($('<textarea class="form-control"/>'), function ($elem) {
            return $elem.val();
        }, function ($elem, value) {
            return $elem.val($elem, value);
        }, function ($elem, value){
            $elem.attr('placeholder', value);
        });
    };

    return module;
});
