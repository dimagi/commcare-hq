var LangcodeValidator = (function () {
    function LangcodeValidator(options) {
        var i,
            that = this;
        this.$home = $("#" + options.home);
        this.langcodes = options.langcodes;
        this.renameURL = options.renameURL;
        this.edit = options.edit;
        this.validation = {
            isValid: {},
            name: {},
            suggestions: {}
        };
        for (i = 0; i < this.langcodes.length; i += 1) {
            LangcodeValidator.validate(this.langcodes[i], function(langcode, match, suggestions){
                that.updateValidation(langcode, match, suggestions);
                that.render();
            });
        }
        this.render();
    }
    LangcodeValidator.validate = function (langcode, callback) {
        var validateURL = "/langcodes/validate.json";
        $.get(validateURL, {"term": langcode}, function(data){
            data = JSON.parse(data);
            callback(langcode, data.match, data.suggestions);
        });
    };
    LangcodeValidator.prototype = {
        renameLanguage: function(oldCode, newCode) {
            var that = this;
            this.langcodes[this.langcodes.indexOf(oldCode)] = newCode;
            $.post(this.renameURL, {oldCode: oldCode, newCode: newCode}, function(){
                LangcodeValidator.validate(newCode, function(langcode, match, suggestions){
                    that.updateValidation(newCode, match, suggestions);
                    that.render();
                });
            });
        },
        render: function () {
            var $table = $("<table></table>"),
                $row,
                $td,
                $a,
                $links,
                i, j, langcode, sughtml, sug,
                that = this;
            for (i = 0; i < this.langcodes.length; i += 1) {
                langcode = this.langcodes[i];
                sughtml = [];
                $links = $("<span>Change to: </span>");
                for (j = 0; j < (this.validation.suggestions[langcode] || []).length; j += 1) {
                    sug = this.validation.suggestions[langcode][j];
                    $a = (function(langcode, sug) {
                        return $("<a href='#'>" + sug.code + " (" + sug.name + ")</a>").click(function(){
                            if (confirm("Are you sure you want to rename unknown language '" + langcode +"' to '" + sug.code + "'?")) {
                                that.renameLanguage(langcode, sug.code);
                            }
                            return false;
                        });
                    }(langcode, sug));
                    $links.append($a);
                    $links.append(", ");
                }
                (function(langcode) {
                    return $("<input type='text' class='langcodes short' />").blur(function(){
                        var code = $(this).val();
                        if (code && confirm("Are you sure you want to rename unknown language '" + langcode +"' to '" + code + "'?")) {
                            that.renameLanguage(langcode, code);
                        }
                    }).langcodes();
                })(langcode).appendTo($links);

//                if (j === 0) {
//                    $links = "";
//                }
                $row = $("<tr></tr>");
                $td = $("<td></td>").html(this.validation.isValid[langcode] ? langcode : "<strike>" + langcode + "</strike>").appendTo($row);
                $td = $("<td></td>").text(this.validation.name[langcode] || "?").appendTo($row);
                if(this.edit) {
                    $td = $("<td></td>").appendTo($row).html(this.validation.isValid[langcode] ? "" : $links);
                }
                $table.append($row);
            }
            this.$home.html("").append($table);
            COMMCAREHQ.initBlock(this.$home);
        },
        updateValidation: function(langcode, match, suggestions){
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