hqDefine('hqwebapp/js/ui_elements/ui-element-input-map', [
    'jquery',
    'hqwebapp/js/main',
], function (
    $,
    hqMain
) {
    'use strict';
    var module = {};

    var InputMap = function (show_del_button, placeholders) {
        var that = this;
        hqMain.eventize(this);
        if (!placeholders) {
            placeholders = {};
            placeholders.key = django.gettext('key');
            placeholders.value = django.gettext('value');
        }
        this.ui = $('<div class="form-group hq-input-map" />');
        this.value = {
            key: "",
            val: "",
        };
        this.edit = true;
        this.show_delete = show_del_button;
        this.on('change', function () {
            this.val(this.ui.find(".enum-key").val(), this.ui.find(".enum-value").val());
        });
        this.on('remove', function () {
            this.ui.remove();
        });

        this.$edit_view = $('<div class="form-inline" style="margin-left:5px;" />');
        var key_input = $('<input type="text" class="form-control enum-key" style="width:220px;" placeholder="' + placeholders.key + '" />'),
            val_input = $('<input type="text" class="form-control enum-value" style="width:220px;" placeholder="' + placeholders.value  + '" />');
        key_input.change(function () {
            that.fire('change');
        });
        val_input.change(function () {
            that.fire('change');
        });
        this.$edit_view.append(key_input);
        this.$edit_view.append(' <i class="fa fa-arrow-right"></i> ');
        this.$edit_view.append(val_input);
        if (this.show_delete) {
            var $deleteButton = $('<a href="#" data-enum-action="remove" class="btn btn-danger" />');
            $deleteButton.append('<i class="fa fa-remove"></i> ' + django.gettext('Delete'));
            $deleteButton.click(function () {
                that.fire('remove');
                return false;
            });
            this.$edit_view.append(' ');
            this.$edit_view.append($deleteButton);
        }
        this.$noedit_view = $('<div />');

        this.setEdit(this.edit);
    };
    InputMap.prototype = {
        val: function (map_key, map_val, translated_map_val) {
            if (map_key === undefined) {
                return this.value;
            } else {
                this.value = {
                    key: map_key,
                    val: map_val,
                };
                this.$edit_view.find(".enum-key").val(map_key);
                this.$edit_view.find(".enum-value").val(map_val);
                if (map_val === "" && translated_map_val !== undefined && translated_map_val !== "") {
                    this.$edit_view.find(".enum-value").attr("placeholder", translated_map_val.value);
                    var $langcodeButton = module.langcode_tag_btn($('<a href="#" class="btn btn-info btn-xs lang-text" />'),
                        translated_map_val.lang);
                    $langcodeButton.button.attr("style", "position: absolute; top: 6px; right: 6px;");
                    this.$edit_view.find(".enum-value").css("position", "relative").after($langcodeButton.button);
                    this.on('change', function () {
                        if (this.$edit_view.find(".enum-value").val() === "")
                            $langcodeButton.button.show();
                        else
                            $langcodeButton.button.hide();
                    });

                }
                if (map_key) {
                    this.$noedit_view.html('<strong>' + $('<div>').text(map_key).html() + '</strong> &rarr; ' + (
                        map_val ? $('<div>').text(map_val).html() : django.gettext('(empty)')
                    ));
                } else {
                    this.$noedit_view.text("");
                }
                return this;
            }
        },
        setEdit: function (edit) {
            this.edit = edit;
            this.$edit_view.detach();
            this.$noedit_view.detach();
            if (this.edit) {
                this.$edit_view.appendTo(this.ui);
            } else {
                this.$noedit_view.appendTo(this.ui);
            }
            return this;
        },
    };

    module.new = function (show_del_button, placeholders) {
        return new InputMap(show_del_button, placeholders);
    };

    return module;

});
