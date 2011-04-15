var LangcodeValidator = (function () {
    function LangcodeValidator(options) {
        var i,
            that = this;
        this.$home = $("#" + options.home);
        this.langcodes = options.langcodes;
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
        render: function () {
            var $table = $("<table></table>"),
                $row,
                $td,
                i, langcode;
            for (i = 0; i < this.langcodes.length; i += 1) {
                langcode = this.langcodes[i];
                $row = $("<tr></tr>");
                $td = $("<td></td>").text(langcode);
                $row.append($td);
                $td = $("<td></td>").text(this.validation.name[langcode] || "");
                $row.append($td);
                $td = $("<td></td>").text(JSON.stringify(this.validation.suggestions[langcode]));
                $table.append($row);
            }
            this.$home.html("").append($table);
        },
        updateValidation: function(langcode, match, suggestions){
            if (match) {
                this.validation.isValid[langcode] = true;
                this.validation.name = match.name;
            } else {
                this.isValid[langcode] = false;
                this.validation.suggestions[langcode] = suggestions;
            }
        }
    };
    return LangcodeValidator;
}());