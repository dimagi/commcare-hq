
hqDefine('hqwebapp/js/ui_elements/bootstrap5/ui-element-input-map', [
    'jquery',
    'underscore',
    'hqwebapp/js/eventize',
    'DOMPurify/dist/purify.min',
], function (
    $,
    _,
    eventize,
    DOMPurify,
) {
    var module = {};

    var InputMap = function (showDelButton, placeholders) {
        var that = this;
        eventize(this);
        if (!placeholders) {
            placeholders = {};
            placeholders.key = gettext('key');
            placeholders.value = gettext('value');
        }
        this.ui = $('<div class="hq-input-map" />');
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

        this.$edit_view = $('<div class="row mb-3"></div>');
        var $keyInputWrapper = $('<div class="col-md-5"></div>'),
            $keyInput = $('<input type="text" class="form-control enum-key" placeholder="' + placeholders.key + '" />'),
            $valInputWrapper = $('<div class="col-md-5"></div>'),
            $valInput = $('<input type="text" class="form-control enum-value" placeholder="' + placeholders.value  + '" />');
        $keyInput.change(function () {
            that.fire('change');
        });
        $valInput.change(function () {
            that.fire('change');
        });
        $keyInputWrapper.append($keyInput);
        this.$edit_view.append($keyInputWrapper);
        this.$edit_view.append('<div class="col-sm-1 px-0 mt-2" style="width: 15px;"><i class="fa fa-arrow-right"></i></div>');
        $valInputWrapper.append($valInput);
        this.$edit_view.append($valInputWrapper);
        if (this.show_delete) {
            var $deleteButton = $('<a href="#" data-enum-action="remove" class="btn btn-outline-danger" />');
            $deleteButton.append('<i class="fa fa-remove"></i> ');
            $deleteButton.click(function () {
                that.fire('remove');
                return false;
            });
            var $deleteButtonWrapper = $('<div class="col-md-1 px-0"></div>');
            $deleteButtonWrapper.append($deleteButton);
            this.$edit_view.append($deleteButtonWrapper);
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
