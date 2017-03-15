/* globals JsDiff, DOMPurify */
hqDefine('app_manager/js/app_diff.js', function () {
    var reverse = hqImport('hqwebapp/js/urllib.js').reverse;
    var sanitize = DOMPurify.sanitize;

    var init = function(selector, appIdOne, appIdTwo) {
        var $el = $(selector);

        if (!$el.length) {
            throw new Error(selector + ' does not resolve to an element');
        }
        return new AppDiff($el, appIdOne, appIdTwo);
    };

    /**
     * AppDiff
     *
     * This class takes in two app ids to compare and generate a diff. The first app id passed in
     * is considered the newer version.
     *
     * $el {Object} - A jquery element that is the destination for the diff
     * appIdOne {String} - An app id
     * appIdTwo {String} - An app id
     */
    var AppDiff = function($el, appIdOne, appIdTwo) {
        var self = this;
        self.appIdOne = appIdOne;
        self.appIdTwo = appIdTwo;
        self.$el = $el;
        self.controller = new Controller();

        /**
         * renderDiff
         *
         * When called renders a diff into the $el element
         */
        self.renderDiff = function() {
            $.when(
                self.controller.getFormData(self.appIdOne),
                self.controller.getFormData(self.appIdTwo)
            ).done(function(formDataOneJson, formDataTwoJson) {
                self.$el.html(self.generateHtmlDiff(formDataOneJson, formDataTwoJson));
                self.$el.find('.diff-questions:not(:has(.diff-change))').html('<i>No changes detected</i>');
            });
        };

        /**
         * generateHtmlDiff
         *
         * Generates an html diff string.
         *
         * formDataOneJson {Object} - Json object representing the app
         * formDataTwoJson {Object} - Json object representing the app
         *
         * returns {String} An html string representing the diff
         */
        self.generateHtmlDiff = function(formDataOneJson, formDataTwoJson) {
            var modulesOne = [],
                modulesTwo = [],
                textOne,
                textTwo,
                header,
                diffObjects,
                totalChanges = { added: 0, removed: 0 },
                fullHtml;
            _.each(formDataOneJson, function(d) {
                modulesOne.push(new ModuleDatum(d));
            });
            _.each(formDataTwoJson, function(d) {
                modulesTwo.push(new ModuleDatum(d));
            });
            textOne = _.map(modulesOne, function(m) { return m.toString(); }).join('\n');
            textTwo = _.map(modulesTwo, function(m) { return m.toString(); }).join('\n');
            diffObjects = JsDiff.diffLines(textTwo, textOne);

            fullHtml = HtmlUtils.makeUl('diff-app fa-ul') + '\n';
            _.each(diffObjects, function(diff) {
                var className = 'diff-no-change';
                if (diff.added) {
                    totalChanges.added += 1;
                    className = 'diff-added diff-change';
                } else if (diff.removed) {
                    totalChanges.removed += 1;
                    className = 'diff-removed diff-change';
                }
                fullHtml += HtmlUtils.replaceStub(diff.value, className);
            });
            fullHtml += HtmlUtils.closeEl('ul');

            header = HtmlUtils.makeSpan(
                totalChanges.added + ' lines added', 'diff-changes-count diff-changes-added'
            );
            header += HtmlUtils.makeSpan(
                totalChanges.removed + ' lines removed', 'diff-changes-count diff-changes-removed'
            );

            return header + fullHtml;
        };
    };

    /**
     * Represents the module data structure and renders it to an HTML string
     */
    var ModuleDatum = function(json) {
        var self = this;
        this.id = json.id;
        this.name = json.name;
        this.shortComment = json.short_comment;
        this.forms = _.map(json.forms, function(form) { return new FormDatum(form); });

        this.toString = function() {
            var lines = [
                HtmlUtils.makeLi(sanitize(self.name.en), 'diff-module', 'folder-open'),
                HtmlUtils.makeUl('diff-forms fa-ul'),
                _.map(self.forms, function(f) { return f.toString(); }).join('\n'),
                HtmlUtils.closeEl('ul'),
                HtmlUtils.closeEl('li'),
            ];
            return lines.join('\n');
        };
    };

    /**
     * Represents the form data structure and renders it to an HTML string
     */
    var FormDatum = function(json) {
        var self = this;
        this.id = json.id;
        this.name = json.name;
        this.shortComment = json.short_comment;
        this.questions = _.map(json.questions, function(q) { return new QuestionDatum(q); });

        this.toString = function() {
            var lines = [
                HtmlUtils.makeLi(sanitize(self.name.en), 'diff-form', 'file-o'),
                HtmlUtils.makeUl('diff-questions fa-ul'),
                _.map(self.questions, function(q) { return q.toString(); }).join('\n'),
                HtmlUtils.closeEl('ul'),
                HtmlUtils.closeEl('li'),
            ];
            return lines.join('\n');
        };
    };

    /**
     * Represents the question data structure and renders it to an HTML string
     */
    var QuestionDatum = function(json) {
        var self = this;
        this.comment = json.comment;
        this.group = json.group;
        this.hashtagValue = json.hashtagValue;
        this.label = json.label;
        this.options = json.options;
        this.relevant = json.relevant;
        this.repeat = json.repeat;
        this.required = json.required;
        this.response = json.response;
        this.tag = json.tag;
        this.translations = json.translations;
        this.type = json.type;
        this.value = json.value;

        this.toString = function() {
            var lines =[
                HtmlUtils.makeLi(sanitize(self.label) || '[unknown]', 'diff-question'),
                HtmlUtils.makeUl('diff-question-metadata fa-ul'),

                HtmlUtils.makeLi(sanitize(self.hashtagValue), '', '', true),
                (self.calculate ? HtmlUtils.makeLi(sanitize(self.calculate), '', 'calculator', true) : ''),
                (self.relevant ? HtmlUtils.makeLi(sanitize(self.relevant), '', 'code-fork', true) : ''),

                HtmlUtils.closeEl('ul'),
                HtmlUtils.closeEl('li'),
            ];
            return lines.join('\n');
        };
    };

    /**
     * Controller used to formd data from the server
     */
    var Controller = function() {
        var cache = {};

        this.getFormData = function(appId) {
            var url = reverse('form_data', appId),
                deferred = $.Deferred();

            if (cache.hasOwnProperty(appId)) {
                deferred.resolve(cache[appId]);
            } else if (!appId) {
                deferred.resolve([]);
            } else {
                $.get(url).done(function(response) {
                    cache[appId] = response.response;
                    deferred.resolve(response.response);
                }).fail(function(response) {
                    deferred.resolve(response);
                });
            }
            return deferred;
        };
    };

    /**
     * Utility functions for building up html elements
     */
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
            return HtmlUtils.makeEl('span', line, className, icon, true);
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
                '<span class="' + HtmlUtils.REPLACE + '" >' + line + '</span>' +
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
        replaceStub: function(line, replace) {
            return line.replace(new RegExp(HtmlUtils.REPLACE, 'g'), replace);
        },
        REPLACE: '###',
    };

    return {
        init: init,
    };
});
