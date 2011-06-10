var mk_translation_ui = function (spec) {
    var that = {
        translations: spec.translations,
        $home: spec.$home,
        url: spec.url,
        lang: spec.lang,
        doc_id: spec.doc_id
    };

    that.inputs = {};
    that.progressIcons = {};
    that.set_translation = function (key, val) {
        that.translations[key] = val;
        that.inputs[key].val(val);
    };
    that.set_progress_state = function (key, code) {
        var ok_icon = 'ui-icon ui-icon-check',
            fail_icon = 'ui-icon ui-icon-notice',
            working_icon = 'ui-icon ui-icon-arrowrefresh-1-w',
            all_icons = [ok_icon, fail_icon, working_icon].join(' '),
            $icon = that.progressIcons[key],
            $input = that.inputs[key];

        $icon.removeClass(all_icons);

        if (code === "normal") {
            $input.removeAttr('disabled');
        } else if (code === "ok") {
            $input.removeAttr('disabled');
            $icon.addClass(ok_icon);
        } else if (code === "fail") {
            $input.removeAttr('disabled');
            $icon.addClass(fail_icon);
        } else if (code === "working") {
            $input.attr('disabled', 'disabled');
            $icon.addClass(working_icon);
        }
    };
    that.render = function () {
        var $table = $("<table></table>"),
            $tr, $td,
            key, keys = [],
            i;
        for (key in that.translations) {
            if (that.translations.hasOwnProperty(key)) {
                keys.push(key);
            }
        }
        keys.sort();
        console.log(keys);
        for (i = 0; i < keys.length; i += 1) {
            key = keys[i];
            $tr = $("<tr></tr>").append(
                $("<td></td>").text(key)
            ).appendTo($table);

            $td = $("<td></td>").appendTo($tr);
            that.progressIcons[key] = $("<div></div>").appendTo($td);

            $td = $("<td></td>").appendTo($tr);
            that.inputs[key] = $("<input type='text' />").val(that.translations[key]).appendTo($td);
            that.inputs[key].change((function (key) {
                return function () {
                    var value = $(this).val();
                    that.set_progress_state(key, 'working');
                    $.ajax({
                        type: "POST",
                        dataType: "json",
                        url: that.url,
                        data: {
                            doc_id: JSON.stringify(that.doc_id),
                            lang: JSON.stringify(that.lang),
                            key: JSON.stringify(key),
                            value: JSON.stringify(value)
                        },
                        context: this,
                        success: function (data) {
                            that.set_progress_state(key, 'ok');
                            that.set_translation(data.key, data.value);
                        },
                        error: function (data) {
                            that.set_progress_state(key, 'fail');
                            that.set_translation(key, that.translations[key]);
                        }
                    });
                };
            }(key)));

        }
        console.log(that.inputs);
        that.$home.html($table);
    };
    that.render();
};