/* globals JsDiff */
hqDefine('app_manager/js/app_diff.js', function () {
    var init = function(selector, formDataOneJson, formDataTwoJson) {
        var $el = $(selector);

        if (!$el.length) {
            throw new Error(selector + ' does not resolve to an element');
        }
        return new AppDiff($el, formDataOneJson, formDataTwoJson);
    };

    var AppDiff = function($el, formDataOneJson, formDataTwoJson) {
        var self = this;
        self.modulesOne = [];
        self.modulesTwo = [];
        self.$el = $el;

        _.each(formDataOneJson, function(d) {
            self.modulesOne.push(new ModuleDatum(d));
        });
        _.each(formDataTwoJson, function(d) {
            self.modulesTwo.push(new ModuleDatum(d));
        });

        self.generateDiff = function() {
            var textOne = _.map(self.modulesOne, function(m) { return m.toString(); }).join('\n');
            var textTwo = _.map(self.modulesTwo, function(m) { return m.toString(); }).join('\n');
            self.diffObjects = JsDiff.diffLines(textOne, textTwo);

            var fullHtml = HtmlUtils.makeUl('diff-app fa-ul') + '\n';
            self.$el.html('');
            _.each(self.diffObjects, function(diff) {
                var color = diff.added ? 'green' : diff.removed ? 'red' : 'black';
                fullHtml += HtmlUtils.replaceStyle(diff.value, 'color: ' + color);
            });
            fullHtml += HtmlUtils.closeEl('ul');
            self.$el.html(fullHtml);
        };
    };

    var ModuleDatum = function(json) {
        var self = this;
        this.id = json.id;
        this.name = json.name;
        this.shortComment = json.short_comment;
        this.forms = _.map(json.forms, function(form) { return new FormDatum(form); });

        this.toString = function() {
            return (
                HtmlUtils.makeLi(self.name.en, 'diff-module', 'folder-open') + '\n' +
                HtmlUtils.makeUl('diff-forms fa-ul') + '\n' +
                _.map(self.forms, function(f) { return f.toString(); }).join('\n') + '\n' +
                HtmlUtils.closeEl('ul') + '\n' +
                HtmlUtils.closeEl('li') + '\n'
            );
        };
    };

    var FormDatum = function(json) {
        var self = this;
        this.id = json.id;
        this.name = json.name;
        this.shortComment = json.short_comment;
        this.questions = _.map(json.questions, function(q) { return new QuestionDatum(q); });

        this.toString = function() {
            return (
                HtmlUtils.makeLi(self.name.en, 'diff-form', 'file-o') + '\n' +
                HtmlUtils.makeUl('diff-questions fa-ul') + '\n' +
                _.map(self.questions, function(q) { return q.toString(); }).join('\n') +
                HtmlUtils.closeEl('ul') + '\n' +
                HtmlUtils.closeEl('li') + '\n'
            );
        };
    };

    var QuestionDatum = function(json) {
        var self = this;
        this.comment = json.comment;
        this.group = json.group;
        this.hashtagValue = json.hashtagValue;
        this.label = json.label;
        this.options = json.optinos;
        this.relevant = json.relevant;
        this.repeat = json.repeat;
        this.required = json.required;
        this.response = json.response;
        this.tag = json.tag;
        this.translations = json.translations;
        this.type = json.type;
        this.value = json.value;

        this.toString = function() {
            return (
                HtmlUtils.makeLi(self.label || '[unknown]', 'diff-question') +
                HtmlUtils.makeUl('diff-question-metadata fa-ul') + '\n' +

                HtmlUtils.makeLi(self.hashtagValue, '', '', true) +
                (self.calculate ? HtmlUtils.makeLi(self.calculate, '', 'calculator', true) : '') + '\n' +
                (self.relevant ? HtmlUtils.makeLi(self.relevant, '', 'code-fork', true) : '') + '\n' +

                HtmlUtils.closeEl('ul') + '\n' +
                HtmlUtils.closeEl('li') + '\n'
            );
        };
    };

    var HtmlUtils = {
        makeOl: function(className, icon) {
            return HtmlUtils.makeEl('ol', '', className, icon);
        },
        makeUl: function(className, icon) {
            return HtmlUtils.makeEl('ul', '', className, icon);
        },
        makeLi: function(line, className, icon, close) {
            return HtmlUtils.makeEl('li', line, className, icon, close);
        },
        makeSpan: function(line, className, icon) {
            return HtmlUtils.makeEl('span', line, className, icon);
        },
        makeEl: function(el, line, className, icon, close) {
            var iconEl = HtmlUtils.makeIcon(icon);
            var closeEl = '';
            if (close) {
                closeEl = HtmlUtils.closeEl(el);
            }
            return (
                '<' + el + ' class="' + className + '">' +
                iconEl +
                '<span style="' + HtmlUtils.REPLACE + '" >' + line + '</span>' +
                closeEl
            );
        },
        makeIcon: function(icon) {
            if (!icon) {
                return '';
            }
            return '<i class="fa fa-' + icon + '"></i>&nbsp;';
        },
        closeOl: function() {
            return HtmlUtils.closeEl('ol');
        },
        closeUl: function() {
            return HtmlUtils.closeEl('ul');
        },
        closeEl: function(el) {
            return '</' + el + '>';
        },
        replaceStyle: function(line, style) {
            return line.replace(new RegExp(HtmlUtils.REPLACE, 'g'), style);
        },
        REPLACE: '###',
    };

    return {
        init: init,
    };
});
