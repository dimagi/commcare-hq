"use strict";
hqDefine('hqwebapp/js/ui_elements/bootstrap3/ui-element-input-map', [
    'jquery',
    'underscore',
    'hqwebapp/js/bootstrap3/main',
    'DOMPurify/dist/purify.min',
], function (
    $,
    _,
    hqMain,
    DOMPurify
) {
    var module = {};

    var InputMap = function (showDelButton, placeholders) {
        var that = this;
        hqMain.eventize(this);
        if (!placeholders) {
            placeholders = {};
            placeholders.key = gettext('key');
            placeholders.value = gettext('value');
        }
        this.ui = $('<div class="form-group hq-input-map" />');
        this.value = {
            key: "",
            val: "",
        };
        this.edit = true;
        this.show_delete = showDelButton;
        this.on('change', function () {
            this.val(this.ui.find(".enum-key").val(), this.ui.find(".enum-value").val());
        });
        this.on('remove', function () {
            this.ui.remove();
        });

        this.$edit_view = $('<div class="form-inline" style="margin-left:5px;" />');
        var keyInput = $('<input type="text" class="form-control enum-key" style="width:220px;" placeholder="' + placeholders.key + '" />'),
            valInput = $('<input type="text" class="form-control enum-value" style="width:220px;" placeholder="' + placeholders.value  + '" />');
        keyInput.change(function () {
            that.fire('change');
        });
        valInput.change(function () {
            that.fire('change');
        });
        this.$edit_view.append(keyInput);
        this.$edit_view.append(' <i class="fa fa-arrow-right"></i> ');
        this.$edit_view.append(valInput);
        if (this.show_delete) {
            var $deleteButton = $('<a href="#" data-enum-action="remove" class="btn btn-danger" />');
            $deleteButton.append('<i class="fa fa-remove"></i> ' + gettext('Delete'));
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
        val: function (mapKey, mapVal, translatedMapVal) {
            if (mapKey === undefined) {
                return this.value;
            } else {
                this.value = {
                    key: mapKey,
                    val: mapVal,
                };
                this.$edit_view.find(".enum-key").val(mapKey);
                this.$edit_view.find(".enum-value").val(mapVal);
                if (mapVal === "" && translatedMapVal !== undefined && translatedMapVal !== "") {
                    this.$edit_view.find(".enum-value").attr("placeholder", translatedMapVal.value);
                    var $langcodeButton = module.langcode_tag_btn($('<a href="#" class="btn btn-info btn-xs lang-text" />'),
                        translatedMapVal.lang);
                    $langcodeButton.button.attr("style", "position: absolute; top: 6px; right: 6px;");
                    this.$edit_view.find(".enum-value").css("position", "relative").after($langcodeButton.button);
                    this.on('change', function () {
                        if (this.$edit_view.find(".enum-value").val() === "") {
                            $langcodeButton.button.show();
                        } else {
                            $langcodeButton.button.hide();
                        }
                    });

                }
                mapKey = _.escape(DOMPurify.sanitize(mapKey));
                mapVal = _.escape(DOMPurify.sanitize(mapVal));
                if (mapKey && !mapKey.trim()) {
                    mapKey = `"<span style="white-space: pre;">${mapKey}</span>"`;
                }
                if (mapVal && !mapVal.trim()) {
                    mapVal = `"<span style="white-space: pre;">${mapVal}</span>"`;
                }
                let leftSide = mapKey ? `<strong>${mapKey}</strong>` : `<i>${gettext('blank')}</i>`;
                let rightSide = mapVal ? mapVal : `<i>${gettext('blank')}</i>`;
                this.$noedit_view.html(`${leftSide} &rarr; ${rightSide}`);
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

    module.new = function (showDelButton, placeholders) {
        return new InputMap(showDelButton, placeholders);
    };

    return module;

});
