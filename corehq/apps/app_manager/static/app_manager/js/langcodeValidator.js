var LangcodeValidator = (function () {
    'use strict';
    var validateURL;
    function LangcodeValidator(options) {
        var i,
            that = this,
            validationsComplete = 0;
        this.$home = $("#" + options.home);
        this.langcodes = options.langcodes;
        this.renameURL = options.renameURL;
        validateURL = options.validateURL;
        this.validation = {
            isValid: {},
            name: {},
            suggestions: {}
        };
        this.isReady = function () {
            return validationsComplete >= this.langcodes.length;
        };

        function validateCallback(langcode, match, suggestions) {
            that.updateValidation(langcode, match, suggestions);
            validationsComplete += 1;
            that.render();
        }
        if (this.langcodes.length) {
            this.$home.html("");
        }
        for (i = 0; i < this.langcodes.length; i += 1) {
            LangcodeValidator.validate(this.langcodes[i], validateCallback);
        }
    }
    LangcodeValidator.validate = function (langcode, callback) {
        $.get(validateURL, {"term": langcode}, function (data) {
            data = JSON.parse(data);
            callback(langcode, data.match, data.suggestions);
        });
    };
    LangcodeValidator.prototype = {
        renameLanguage: function (oldCode, newCode) {
            var that = this,
                i = this.langcodes.indexOf(oldCode);
            this.langcodes[i] = newCode;
            $.ajax({
                url: this.renameURL,
                type: "POST",
                data: {oldCode: oldCode, newCode: newCode},
                dataType: "json",
                beforeSend: function () {
                    that.disable();
                },
                success: function () {
                    LangcodeValidator.validate(newCode, function (langcode, match, suggestions) {
                        that.updateValidation(newCode, match, suggestions);
                        that.render();
                        that.enable();
                    });
                },
                error: function (response) {
                    var data = JSON.parse(response.responseText);
                    that.$home.html(
                        $("<p/>").text("An error has occurred: " + data.message + ". Please reload")
                    );
                    that.enable();
                }
            });
        },
        disable: function () {
            var p = this.$home.position();
            this.$shield = $('<div/>').text("Working...").css({
                position: 'absolute',
                top: p.top,
                left: p.left,
                zIndex: 1001,
                backgroundColor: '#CCC',
                opacity: 0.4,
                border: '1px solid #888',
                fontSize: '4em',
                textAlign: 'center'
            }).appendTo('body');
            this.$shield.css({
                width: Math.max(this.$shield.width(), this.$home.width()),
                height: Math.max(this.$shield.height(), this.$home.height())
            });
        },
        enable: function () {
            this.$shield.fadeOut(function () { $(this).remove(); });
        },
        render: function () {
            if (!this.isReady()) {
                return;
            }
            var i, j, langcode, sughtml, sug,
                $table = $('<table class="table table-striped"></table>'),
                $row,
                $a,
                $links,
                that = this;

            function getChangeSpecificLanguageLink(langcode, sug) {
                return $("<a href='#'>" + sug.code + " (" + sug.name + ")</a>").click(function (e) {
                    e.preventDefault();
                    COMMCAREHQ.confirm({
                        title: "Rename Language",
                        message: "Are you sure you want to rename language '" + langcode + "' to '" + sug.code + "'?",
                        ok: function () {
                            that.renameLanguage(langcode, sug.code);
                        }
                    });
                    return false;
                });
            }
            function getChangeCustomLanguageLink(langcode) {
                var $a = $('<a href="#"/>').text('Choose Language').click(function (e) {
                    e.preventDefault();

                    var $input = $("<input type='text' class='langcodes short' />").langcodes(),
                        $requiredMessage = $("<div/>");

                    COMMCAREHQ.confirm({
                        title: "Change Language",
                        message: function () {
                            var $text = $('<span/>').text('Rename language "' + langcode + '" to '),
                                $span = $('<span/>').append($requiredMessage, $text, $input);
                            COMMCAREHQ.initBlock($span);
                            $span.appendTo(this);
                        },
                        open: function () {
                            $input.focus();
                        },
                        ok: function () {
                            var code = $input.val();
                            if (code) {
                                that.renameLanguage(langcode, code);
                            } else {
                                $(this).dialog('open');
                                $requiredMessage.text("You must enter in a language code");
                            }
                        }
                    });
                });
                return $a;
            }
            for (i = 0; i < this.langcodes.length; i += 1) {
                langcode = this.langcodes[i];
                sughtml = [];
                $links = $("<span>Change to: </span>");
                for (j = 0; j < (this.validation.suggestions[langcode] || []).length; j += 1) {
                    sug = this.validation.suggestions[langcode][j];
                    $a = getChangeSpecificLanguageLink(langcode, sug);
                    $links.append($a);
                    $links.append(", ");
                }
                getChangeCustomLanguageLink(langcode).appendTo($links);

                $row = $("<tr></tr>");
                $("<td/>").html(this.validation.isValid[langcode] ?
                    langcode : '<strike>' + langcode + '</strike>').appendTo($row);
                $('<td/>').append(
                    $('<i/>').addClass(this.validation.isValid[langcode] ? 'icon-ok' : 'icon-exclamation-sign')
                ).appendTo($row);
                $("<td/>").html(this.validation.name[langcode] || "").appendTo($row);
                $("<td></td>").appendTo($row).html($links);
                $table.append($row);
            }
            this.$home.html("").append($table);
            COMMCAREHQ.initBlock(this.$home);
        },
        updateValidation: function (langcode, match, suggestions) {
            if (match) {
                this.validation.isValid[langcode] = true;
                this.validation.name[langcode] = match.name;
            } else {
                this.validation.isValid[langcode] = false;
                this.validation.suggestions[langcode] = suggestions;
            }
        }
    };
    return LangcodeValidator;
}());
