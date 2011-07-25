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
        ps = {
            normal: 'normal',
            ok: 'ok',
            fail: 'fail',
            working: 'working',
            just_added: 'just_added'
        },
        key,
        Translation = (function () {
            var Translation = function (key, value) {
                this.key = key;
                this.value = value;
                this.$icon = $("<div></div>");
                this.progressState = ps.normal;
            };
            Translation.init = function (key, value) {
                return new Translation(key, value);
            };
            Translation.prototype = {
                initInput: function ($td) {
                    if (translation_ui.edit) {
                        this.$input = $("<input type='text' />").val(this.value);
                    } else {
                        this.$input = $("<span></span>").text(this.value);
                    }
                    this.$input.appendTo($td);
                    if (translation_ui.edit) {
                        var that = this;
                        this.$input.change(function () {
                            that.handleInputChange();
                        });
                    }
                },
                setProgressState: function (progressState) {
                    var ok_icon = 'ui-icon ui-icon-check',
                        fail_icon = 'ui-icon ui-icon-notice',
                        working_icon = 'ui-icon ui-icon-arrowrefresh-1-w',
                        just_added_icon = 'ui-icon ui-icon-document',
                        all_icons = [ok_icon, fail_icon, working_icon, just_added_icon].join(' '),
                        $icon = this.$icon,
                        $input = this.$input;

                    $icon.removeClass(all_icons);

                    if (progressState === ps.normal) {
                        $input.removeAttr('disabled');
                    } else if (progressState === ps.ok) {
                        $input.removeAttr('disabled');
                        $icon.addClass(ok_icon);
                    } else if (progressState === ps.fail) {
                        $input.removeAttr('disabled');
                        $icon.addClass(fail_icon);
                    } else if (progressState === ps.working) {
                        $input.attr('disabled', 'disabled');
                        $icon.addClass(working_icon);
                    } else if (progressState === ps.just_added) {
                        $input.removeAttr('disabled');
                        $icon.addClass(just_added_icon);
                    }
                    this.progressState = progressState;
                },
                setValue: function (val) {
                    this.value = val;
                    this.$input.val(val);
                },
                handleInputChange: function () {
                    var value = this.$input.val();
                    if (!value) {
                        value = (
                            confirm("You this box blank. Would you like to delete the key '" + this.key + "'?") ?
                            null : ""
                        );
                    }
                    this.setProgressState(ps.working);
                    $.ajax({
                        type: "POST",
                        dataType: "json",
                        url: translation_ui.url,
                        data: {
                            doc_id: JSON.stringify(translation_ui.doc_id),
                            lang: JSON.stringify(translation_ui.lang),
                            key: JSON.stringify(this.key),
                            value: JSON.stringify(value)
                        },
                        context: this,
                        success: function (data) {
                            this.setProgressState('ok');
                            this.setValue(data.value);
                            if (this.value === null) {
                                delete translation_ui.translations[this.key];
                                translation_ui.render();
                            }
                            COMMCAREHQ.updateDOM(data.update);
                        },
                        error: function () {
                            this.setProgressState('fail');
                            this.setValue(this.value);
                        }
                    });
                }
            };
            return Translation;
        }());

    for (key in spec.translations) {
        if (spec.translations.hasOwnProperty(key)) {
            translation_ui.translations[key] = Translation.init(key, spec.translations[key]);
        }
    }

    translation_ui.translate = function (key) {
        return translation_ui.translations[key].value;
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
                translation.$icon.appendTo($td);

                $td = $("<td></td>").appendTo($tr);
                translation.initInput($td);
            }
            translation_ui.$home.html($table);
        } else {
            translation_ui.$home.html($("<p>No translations</p>"));
        }
        translation_ui.$home.append(
            translation_ui.edit ?
                $("<a href='#'><span class='ui-icon ui-icon-plusthick'></span>Translation</a>").click(function () {
                    var key = prompt("Key: ");
                    if (key && !translation_ui.translations[key]) {
                        translation_ui.translations[key] = Translation.init(key, "");
                        translation_ui.render();
                        translation_ui.translations[key].$input.focus();
                        translation_ui.translations[key].setProgressState(ps.just_added);
                    } else if (key) {
                        alert("The key '" + key + "' is already used");
                    }
                    return false;
                }) : null
        );
    };
    translation_ui.render();
    
};