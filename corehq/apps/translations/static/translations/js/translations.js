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
                this.key = uiElement.input().val(key).setEdit(false);
                this.value = uiElement.input().val(value).setEdit(translation_ui.edit);
            };
            Translation.init = function (key, value) {
                return new Translation(key, value);
            };
            Translation.prototype = {
                initInput: function ($td) {
                    var that = this;
                    this.value.ui.appendTo($td);
                    this.value.on('change', function () {
                        that.handleInputChange();
                    });
                },
                handleInputChange: function () {
                    var value = this.value.val();
                    if (!value) {
                        value = (
                            confirm("You this box blank. Would you like to delete the key '" + this.key.val() + "'?") ?
                            null : ""
                        );
                    }
                    translation_ui.saveButton.fire('change');
                }
            };
            return Translation;
        }()),
        $home = $('<div/>');

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
        var key, data = [];
        for (key in translation_ui.translations) {
            if (translation_ui.translations.hasOwnProperty(key)) {
                data.push({
                    key: translation_ui.translations[key].key.val(),
                    value: translation_ui.translations[key].value.val()
                });
            }
        }
        this.saveButton.ajax({
            type: "POST",
            dataType: "json",
            url: translation_ui.url,
            data: {
                doc_id: translation_ui.doc_id,
                lang: translation_ui.lang,
                translations: JSON.stringify(data)
            },
            context: this,
            success: function (data) {
                this.setValue(data.value);
                if (this.value === null) {
                    delete translation_ui.translations[this.key.val()];
                    translation_ui.render();
                }
                COMMCAREHQ.updateDOM(data.update);
            }
        });
    };

    translation_ui.render = function () {
        var $table = $("<table></table>"),
            $tr,
            $td,
            key,
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
                $tr = $("<tr></tr>").append(
                    $("<td></td>").append($("<code></code>").text(key))
                ).appendTo($table);
                $td = $("<td></td>").appendTo($tr);
                translation.initInput($td);
            }
            $home.html($table);
        } else {
            translation_ui.$home.html($("<p>No translations</p>"));
        }
        $home.append(
            translation_ui.edit ?
                $("<a href='#'><span class='ui-icon ui-icon-plusthick'></span>Translation</a>").click(function () {
                    var key = prompt("Key: ");
                    if (key && !translation_ui.translations[key]) {
                        translation_ui.translations[key] = Translation.init(key, "");
                        translation_ui.render();
                        translation_ui.translations[key].value.ui.focus();
                    } else if (key) {
                        alert("The key '" + key + "' is already used");
                    }
                    return false;
                }) : null
        );
    };
    translation_ui.render();
};