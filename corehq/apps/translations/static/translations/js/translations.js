var mk_translation_ui = function (spec) {
    "use strict";
    var translation_ui = {
            translations: {},
            $home: spec.$home,
            url: spec.url,
            lang: spec.lang,
            doc_id: spec.doc_id,
            edit: spec.edit,
            allow_autofill: spec.allow_autofill
        },
        suggestionURL = spec.suggestion_url,
        suggestionCache = {},
        key,
        Translation = (function () {
            var Translation = function (key, value) {
                var that = this;
                this.key = uiElement.input().val(key).setEdit(false);
                this.value = uiElement.input().val(value).setEdit(translation_ui.edit);
                this.solid = true;

                this.$delete = $('<i></i>').addClass(COMMCAREHQ.icons.DELETE).click(function () {
                    $(this).remove();
                    translation_ui.deleteTranslation(that.key.val());
                }).css({cursor: 'pointer'}).attr('title', "Delete Translation");
                
                this.$add = $('<i></i>').addClass(COMMCAREHQ.icons.ADD).click(function () {
                    // remove any trailing whitespace from the input box
                    that.key.val($.trim(that.key.val()));
                    if (that.key.val() && !translation_ui.translations[that.key.val()]) {
                        var hasError = translation_ui.addTranslation(that);
                        if (!hasError) {
                            translation_ui.appendAdder();
                        }
                    } else {
                        that.key.$edit_view.focus();
                    }
                }).css({cursor: 'pointer'}).attr('title', "Add Translation").hide();
                this.$error = $('<span></span>').addClass('alert alert-error');
                this.ui = $('<tr/>');
                $('<td/>').append(this.key.ui).appendTo(this.ui);
                $('<td/>').append(this.value.ui).appendTo(this.ui);
                $('<td/>').append(this.$delete).appendTo(this.ui);
                $('<td/>').append(this.$add).appendTo(this.ui);
                $('<td/>').append(this.$error).appendTo(this.ui);
                this.$error.hide()
                if (!translation_ui.edit) {
                    this.$delete.hide();
                    this.$add.hide();
                    this.$error.hide();
                }

                var helperFunction = function () {
                    if (that.solid) {
                        translation_ui.saveButton.fire('change');
                    }
                };

                this.value.on('change', helperFunction);

                this.value.ui.find('input').autocomplete({
                    select: helperFunction
                });

                this.value.ui.find('input').focus(function () {
                    var input = $(this);
                    if (!suggestionCache.hasOwnProperty('-' + that.key.val())) {
                        $.ajax({
                            type: "get",
                            url: suggestionURL,
                            data: {
                                lang: translation_ui.lang,
                                key: that.key.val()
                            },
                            dataType: "json",
                            success: function (data) {
                                suggestionCache['-' + that.key.val()] = data;
                                input.autocomplete({
                                    source: function(request, response) {
                                        response($.ui.autocomplete.filter(suggestionCache['-' + that.key.val()], ''));
                                    },
                                    minLength: 0
                                });
                                input.autocomplete('search');
                            }
                        });
                    } else {
                        input.autocomplete('search');
                    }
                })
                
            };
            Translation.init = function (key, value) {
                return new Translation(key, value);
            };
            Translation.prototype = {
                setSolid: function (solid) {
                    this.solid = solid;
                    if (solid) {
                        this.key.setEdit(false);
                        this.$delete.show();
                        this.$add.hide();
                    } else {
                        this.key.setEdit(true);
                        this.$delete.hide();
                        this.$add.show();
                    }
                }
            };
            return Translation;
        }()),
        $home = $('<div/>'),
        $table = $("<table></table>"),
        $list_tbody = $('<tbody/>').appendTo($table),
        $adder_tbody = $('<tbody/>').appendTo($table),
        $bootstrap = $('<a/>').attr('href', '').text('Auto fill translations').click(function (e) {
            e.preventDefault();
            $.ajax({
                type: "get",
                url: suggestionURL,
                dataType: "json",
                data: {
                    lang: translation_ui.lang,
                    one: true
                },
                success: function (data) {
                    var key;
                    for (key in data) {
                        if (data.hasOwnProperty(key) && !translation_ui.translations[key]) {
                            translation_ui.addTranslation(Translation.init(key, data[key]));
                        }
                    }
                }
            });
        }).after($('<a style="padding-left: 6px;"><i class="icon-question-sign" data-trigger="click"></i></a>')).popover({
            placement: 'right',
            title: 'Auto Fill translations',
            content: 'This will pick the most common translations for your selected language.  You can then edit them as needed.'
        });

    for (key in spec.translations) {
        if (spec.translations.hasOwnProperty(key)) {
            translation_ui.translations[key] = Translation.init(key, spec.translations[key]);
        }
    }

    translation_ui.saveButton = COMMCAREHQ.SaveButton.init({
        unsavedMessage: "You have unsaved user interface translations.",
        save: function () {
            translation_ui.save()
        }
    });
    if (translation_ui.edit) {
        translation_ui.$home.prepend(translation_ui.saveButton.ui);
    }
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
                    translation_ui.translations[key].$error.text('Parameters formatting problem!');
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
                    translations: JSON.stringify(data)
                },
                context: this,
                success: function (data) {
                    COMMCAREHQ.updateDOM(data.update);
                }
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
            $list_tbody.append(translation.ui.hide());
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
        $adder_tbody.append(adder.ui);
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
                translation.ui.appendTo($list_tbody);
            }
        } else if (!translation_ui.edit) {
            $home.append($("<p>No translations</p>"));
        }
        if (translation_ui.edit) {
            if (translation_ui.allow_autofill) {
                $home.append($bootstrap);
            }
            translation_ui.appendAdder();
        }
        $home.append($table);
    };
    translation_ui.validate_translation = function(translation) {
        var patt = /\$.*?}/g;
        var parameters = translation.value.val().match(patt);
        var error = false;
        if (parameters !== null && parameters.length !== 0) {
            var patt2 = /\$\{[0-9]+}/;
            for (var idx in parameters) {
                if(!parameters[idx].match(patt2)) {
                    error = true;
                }
            }
        }
        return error
    }
    translation_ui.render();
};