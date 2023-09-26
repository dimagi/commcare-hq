hqDefine("translations/js/translations", [
    'jquery',
    'underscore',
    'hqwebapp/js/bootstrap3/main',
    'hqwebapp/js/ui_elements/bootstrap3/ui-element-input',
    'hqwebapp/js/ui_elements/bootstrap3/ui-element-select',
], function (
    $,
    _,
    hqMain,
    UIInput,
    UISelect
) {
    var mk_translation_ui = function (spec) {
        "use strict";
        var translation_ui = {
                translations: {},
                $home: spec.$home,
                url: spec.url,
                lang: spec.lang,
                doc_id: spec.doc_id,
                edit: spec.edit,
                allow_autofill: spec.allow_autofill,
            },
            suggestionURL = spec.suggestion_url,
            suggestionCache = {},
            key,
            Translation = (function () {
                var Translation = function (key, value) {
                    var self = this;
                    self.key = UIInput.new().val(key).setEdit(false);
                    var options = value ? [{label: value, value: value}] : [];
                    self.value = UISelect.new(options);
                    if (value) {
                        self.value.val(value);
                    }
                    self.solid = true;

                    self.$delete = $('<button class="btn btn-danger"><i class="fa fa-remove"></i></button>').click(function () {
                        $(this).remove();
                        translation_ui.deleteTranslation(self.key.val());
                    }).css({
                        cursor: 'pointer',
                    }).attr('title', gettext("Delete Translation"));

                    self.$add = $('<button class="btn btn-default"><i class="fa fa-plus"></i></button>').click(function () {
                        // remove any trailing whitespace from the input box
                        self.key.val($.trim(self.key.val()));
                        if (self.key.val() && !translation_ui.translations[self.key.val()]) {
                            var hasError = translation_ui.addTranslation(self);
                            if (!hasError) {
                                translation_ui.appendAdder();
                            }
                        } else {
                            self.key.$edit_view.focus();
                        }
                    }).css({
                        cursor: 'pointer',
                    }).attr('title', gettext("Add Translation")).hide();
                    self.$error = $('<span></span>').addClass('label label-danger');
                    self.ui = $('<div/>').addClass("row").addClass("form-group");
                    $('<div/>').addClass("col-sm-3").append(self.key.ui).appendTo(self.ui);
                    $('<div/>').addClass("col-sm-3").append(self.value.ui).appendTo(self.ui);
                    $('<div/>').addClass("col-sm-1").append(self.$delete).append(self.$add).appendTo(self.ui);
                    $('<div/>').addClass("col-sm-5").append(self.$error).appendTo(self.ui);
                    self.ui = $('<div/>').append(self.ui);
                    self.$error.hide();

                    var helperFunction = function () {
                        if (self.solid) {
                            translation_ui.saveButton.fire('change');
                        }
                    };

                    self.value.on('change', helperFunction);

                    self.value.ui.find('select').select2({
                        minimumInputLength: 0,
                        allowClear: 1,
                        placeholder: ' ', // allowClear requires a placeholder
                        tags: true,
                        width: '100%',
                        ajax: {
                            delay: 100,
                            url: suggestionURL,
                            data: function () {
                                return {
                                    lang: translation_ui.lang,
                                    key: self.key.val(),
                                };
                            },
                            processResults: function (data) {
                                return {
                                    results: _.map(_.compact(data), function (item) {
                                        return {
                                            id: item,
                                            text: item,
                                        };
                                    }),
                                };
                            },
                        },
                    });
                };
                Translation.init = function (key, value) {
                    return new Translation(key, value);
                };
                Translation.prototype = {
                    setSolid: function (solid) {
                        var self = this;
                        self.solid = solid;
                        if (solid) {
                            self.ui.find("legend").closest(".row").remove();
                            self.key.setEdit(false);
                            self.$delete.show();
                            self.$add.hide();
                        } else {
                            self.ui.prepend("<div class='row'><div class='col-sm-12'><legend>" +
                                gettext("Add Translation") + "</legend></div></div>");
                            self.key.setEdit(true);
                            self.$delete.hide();
                            self.$add.show();
                        }
                    },
                };
                return Translation;
            }()),
            $home = $('<div/>'),
            $list = $('<div/>').appendTo($home),
            $adder = $('<div/>').appendTo($home),
            $autoFill = $('<a/>').attr('href', '').attr('class', 'btn btn-primary').text(gettext('Auto fill translations'));
        $autoFill.click(function (e) {
            e.preventDefault();
            $.ajax({
                type: "get",
                url: suggestionURL,
                dataType: "json",
                data: {
                    lang: translation_ui.lang,
                    one: true,
                },
                success: function (data) {
                    var key;
                    for (key in data) {
                        if (data.hasOwnProperty(key) && !translation_ui.translations[key]) {
                            translation_ui.addTranslation(Translation.init(key, data[key]));
                        }
                    }
                },
            });
        });
        var $autoFillHelp = "<span class='auto-fill-help hq-help-template' data-placement='right' " +
            "data-title='" + gettext("Auto Fill translations") + "' " + "data-content='" +
            gettext("This will pick the most common translations for your selected language. " +
                "You can then edit them as needed.") +
            "'></span>";

        for (key in spec.translations) {
            if (spec.translations.hasOwnProperty(key)) {
                translation_ui.translations[key] = Translation.init(key, spec.translations[key]);
            }
        }

        translation_ui.saveButton = hqMain.initSaveButton({
            unsavedMessage: gettext("You have unsaved user interface translations."),
            save: function () {
                translation_ui.save();
            },
        });
        translation_ui.$home.prepend(translation_ui.saveButton.ui);
        translation_ui.$home.append($home);

        translation_ui.translate = function (key) {
            return translation_ui.translations[key].value.val();
        };

        translation_ui.save = function () {
            var key, data = {};
            var error = false;
            for (key in translation_ui.translations) {
                if (translation_ui.translations.hasOwnProperty(key)) {
                    if (translation_ui.validate_translation(translation_ui.translations[key])) {
                        translation_ui.translations[key].$error.text(gettext('Parameters formatting problem!'));
                        translation_ui.translations[key].$error.show();
                        error = true;
                    } else {
                        translation_ui.translations[key].$error.hide();
                        data[translation_ui.translations[key].key.val()] = translation_ui.translations[key].value.val();
                    }
                }
            }
            if (!error) {
                this.saveButton.ajax({
                    type: "POST",
                    dataType: "json",
                    url: translation_ui.url,
                    data: {
                        doc_id: JSON.stringify(translation_ui.doc_id),
                        lang: JSON.stringify(translation_ui.lang),
                        translations: JSON.stringify(data),
                    },
                    context: this,
                    success: function (data) {
                        hqMain.updateDOM(data.update);
                    },
                });
            }
        };

        translation_ui.deleteTranslation = function (key) {
            translation_ui.saveButton.fire('change');
            this.translations[key].ui.fadeOut(function () {
                $(this).remove();
            });
            delete this.translations[key];
        };

        translation_ui.addTranslation = function (translation) {
            var error = translation_ui.validate_translation(translation);
            if (!error) {
                translation.$error.hide();
                translation_ui.saveButton.fire('change');
                translation_ui.translations[translation.key.val()] = translation;
                translation.ui.detach();
                translation.setSolid(true);
                $list.append(translation.ui.hide());
                translation.ui.fadeIn();
            } else {
                translation.$error.text('Parameters formatting problem!');
                translation.$error.show();
            }

            return error;
        };

        translation_ui.appendAdder = function () {
            var adder = Translation.init("", "");
            adder.setSolid(false);
            $adder.append(adder.ui);
        };
        translation_ui.render = function () {
            var key,
                keys = [],
                translation,
                i;
            for (key in translation_ui.translations) {
                if (translation_ui.translations.hasOwnProperty(key)) {
                    keys.push(key);
                }
            }
            keys.sort();
            if (keys.length) {
                for (i = 0; i < keys.length; i += 1) {
                    key = keys[i];
                    translation = translation_ui.translations[key];
                    translation.ui.appendTo($list);
                }
            }

            $home.append($autoFill);
            $home.append($autoFillHelp);

            if (!translation_ui.allow_autofill) {
                $autoFill.attr('class', 'disabled btn btn-primary');
                $('.auto-fill-help').attr('data-content', gettext("Autofill is not available in English (en). " +
                    "Please change your language using the dropdown in the top left."));
            }
            hqMain.transformHelpTemplate($('.auto-fill-help'), true);
            translation_ui.appendAdder();
            $home.append($home);
        };
        translation_ui.validate_translation = function (translation) {
            var patt = /\$.*?}/g;
            var parameters = translation.value.val().match(patt);
            var error = false;
            if (parameters !== null && parameters.length !== 0) {
                var patt2 = /\$\{[0-9]+}/;
                for (var idx in parameters) {
                    if (!parameters[idx].match(patt2)) {
                        error = true;
                    }
                }
            }
            return error;
        };
        translation_ui.render();
    };

    return {
        makeTranslationUI: mk_translation_ui,
    };
});
