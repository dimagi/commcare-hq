var mk_translation_ui = function (spec) {
    "use strict";
    var translation_ui = {
            translations: {},
            $home: spec.$home,
            url: spec.url,
            lang: spec.lang,
            doc_id: spec.doc_id,
            edit: spec.edit
        },
        key,
        Translation = (function () {
            var Translation = function (key, value) {
                var that = this;
                this.key = uiElement.input().val(key).setEdit(false);
                this.value = uiElement.input().val(value).setEdit(translation_ui.edit);
                this.solid = true;

                this.$delete = $('<div class="ui-icon"/>').addClass(COMMCAREHQ.icons.DELETE).click(function () {
                    $(this).remove();
                    translation_ui.deleteTranslation(that.key.val());
                }).css({cursor: 'pointer'}).attr('title', "Delete Translation");
                
                this.$add = $('<div class="ui-icon"/>').addClass(COMMCAREHQ.icons.ADD).click(function () {
                    if (that.key.val() && !translation_ui.translations[that.key.val()]) {
                        translation_ui.addTranslation(that);
                    } else {
                        that.key.$edit_view.focus();
                    }
                }).css({cursor: 'pointer'}).attr('title', "Add Translation").hide();

                this.ui = $('<tr/>');
                $('<td/>').append(this.key.ui).appendTo(this.ui);
                $('<td/>').append(this.value.ui).appendTo(this.ui);
                $('<td/>').append(this.$delete).appendTo(this.ui);
                $('<td/>').append(this.$add).appendTo(this.ui);

                this.value.on('change', function () {
                    if (that.solid) {
                        console.log('ok');
                        translation_ui.saveButton.fire('change');
                    }
                });
                
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
        $table = $("<table></table>");

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
        for (key in translation_ui.translations) {
            if (translation_ui.translations.hasOwnProperty(key)) {
                data[translation_ui.translations[key].key.val()] = translation_ui.translations[key].value.val();
            }
        }
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
    };

    translation_ui.deleteTranslation = function (key) {
        translation_ui.saveButton.fire('change');
        this.translations[key].ui.fadeOut(function () {
            $(this).remove();
        });
        delete this.translations[key];
    };

    translation_ui.addTranslation = function (translation) {
        translation_ui.saveButton.fire('change');
        translation_ui.translations[translation.key.val()] = translation;
        translation.ui.hide();
        translation.setSolid(true);
        translation_ui.appendAdder();
        translation.ui.fadeIn();
    };

    translation_ui.appendAdder = function () {
        var adder = Translation.init("", "");
        adder.setSolid(false);
        $table.append(adder.ui);
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
                translation.ui.appendTo($table);
            }
            $home.html($table);
        } else {
            translation_ui.$home.html($("<p>No translations</p>"));
        }
        translation_ui.appendAdder();
    };
    translation_ui.render();
};