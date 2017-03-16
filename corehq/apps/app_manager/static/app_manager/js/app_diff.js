/* globals JsDiff, DOMPurify */

/**
 * Diff generation is very fragile. Since the diff generated takes in a body of text
 * and returns Change objects back (https://github.com/kpdecker/jsdiff#change-objects).
 * It's very difficult to create an HTML structure to
 * layout the app in a logical way. To hack around this, we diff by line and include
 * the html in the diff algorithm in a specific manner. For example, consider these two
 * pieces of text:
 *
 * <ul>
 *   <li>Form One
 *   </li>
 * </ul>
 *
 * <ul>
 *   <li>Form Two
 *   </li>
 * </ul>
 *
 * The diff generator will give us back objects that when compiled will look like:
 *
 * <ul>
 *   <li>Form One
 *   <li>Form Two
 *   </li>
 * </ul>
 *
 * Which is looks to be invalid HTML. However, the browser interprets different element errors
 * in different ways. In this scenario the browser will smartly close the tag around the li.
 * This is not the case for other elements:
 *
 * > d.innerHTML = '<li>one<li>two'
 * > "<li>one<li>two"
 * > d.innerHTML
 * > "<li>one</li><li>two</li>"
 *
 * > d.innerHTML = '<div>one<div>two'
 * > "<div>one<div>two"
 * > d.innerHTML
 * > "<div>one<div>two</div></div>"
 *
 * Notice how the browser autocorrects the end tag differently. This works out well for us
 * and is taken advantage of in this code.
 * */
hqDefine('app_manager/js/app_diff.js', function () {
    var reverse = hqImport('hqwebapp/js/urllib.js').reverse;
    var sanitize = DOMPurify.sanitize;

    var init = function(selector, options) {
        var $el = $(selector);

        if (!$el.length) {
            throw new Error(selector + ' does not resolve to an element');
        }
        return new AppDiff($el, options);
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
    var AppDiff = function($el, options) {
        var self = this;
        self.$el = $el;
        self.controller = new Controller();
        self.options = options || {};
        _.defaults(self.options, {
            lang: 'en',
        });

        /**
         * renderDiff
         *
         * When called renders a diff into the $el element
         */
        self.renderDiff = function(appIdOne, appIdTwo) {
            self.$el.text(gettext('Crunching app diff...'));
            $.when(
                self.controller.getFormData(appIdOne),
                self.controller.getFormData(appIdTwo)
            ).done(function(formDataOneJson, formDataTwoJson) {
                try {
                    self.$el.html(self.generateHtmlDiff(formDataOneJson, formDataTwoJson));
                    self.$el.find('.diff-questions:not(:has(.diff-change))').html(
                        '<i>' + gettext('No changes detected') + '</i>'
                    );
                } catch (e) {
                    self.showError();
                    throw e;
                }
            }).fail(function() {
                self.showError();
            });
        };

        self.showError = function() {
            self.$el.text(gettext('Error generating the application diff. Please report an issue.'));
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
                modulesOne.push(new ModuleDatum(d, self.options));
            });
            _.each(formDataTwoJson, function(d) {
                modulesTwo.push(new ModuleDatum(d, self.options));
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
                totalChanges.added + ' changes added', 'diff-changes-count diff-changes-added'
            );
            header += HtmlUtils.makeSpan(
                totalChanges.removed + ' changes removed', 'diff-changes-count diff-changes-removed'
            );

            return header + fullHtml;
        };
    };

    /**
     * Represents the module data structure and renders it to an HTML string
     */
    var ModuleDatum = function(json, options) {
        var self = this;
        this.id = json.id;
        this.name = json.name;
        this.options = options;
        this.shortComment = json.short_comment || '';
        this.forms = _.map(json.forms, function(form) { return new FormDatum(form, self.options); });

        this.toString = function() {
            var lines = [
                // We want these to be considered one line
                (
                    HtmlUtils.makeLi(sanitize(self.name[self.options.lang]), 'diff-module', 'folder-open') +
                    HtmlUtils.makeSpan(' ' + sanitize(self.shortComment), 'diff-comment', '', true)
                ),
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
    var FormDatum = function(json, options) {
        var self = this;
        this.id = json.id;
        this.name = json.name;
        this.options = options;
        this.shortComment = json.short_comment || '';
        this.questions = _.map(json.questions, function(q) { return new QuestionDatum(q, self.options); });

        this.toString = function() {
            var lines = [
                // We want these to be considered one line
                (
                    HtmlUtils.makeLi(sanitize(self.name[self.options.lang]), 'diff-form', 'file-o') +
                    HtmlUtils.makeSpan(sanitize(' ' + self.shortComment), 'diff-comment', '', true)
                ),
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
    var QuestionDatum = function(json, options) {
        var self = this;
        this.comment = json.comment || '';
        this.group = json.group;
        this.hashtagValue = json.hashtagValue;
        this.label = json.label;
        this.options = json.options || [];
        this.relevant = json.relevant;
        this.repeat = json.repeat;
        this.required = json.required;
        this.response = json.response;
        this.tag = json.tag;
        this.translations = json.translations;
        this.type = json.type;
        this.value = json.value;
        this.options = options;

        this.toString = function() {
            var lines =[
                // We want these to be considered one line
                (
                    HtmlUtils.makeLi(sanitize(self.label) || gettext('[unknown]'), 'diff-question') +
                    HtmlUtils.makeSpan(sanitize(' ' + self.comment), 'diff-comment', '', true)
                ),

                HtmlUtils.makeUl('diff-question-metadata fa-ul'),

                HtmlUtils.makeLi(sanitize(self.hashtagValue), '', '', true),
                (self.calculate ? HtmlUtils.makeLi(sanitize(self.calculate), '', 'calculator', true) : ''),
                (self.relevant ? HtmlUtils.makeLi(sanitize(self.relevant), '', 'code-fork', true) : ''),
            ];
            if (self.options.length) {
                lines = lines.concat([
                    HtmlUtils.makeUl('diff-question-options fa-ul'),
                    _.map(
                        self.options,
                        function(option) { return HtmlUtils.makeLi(sanitize(option.value), '', '', true); }
                    ).join('\n'),
                    HtmlUtils.closeEl('ul'),
                ]);
            }

            lines = lines.concat([
                HtmlUtils.closeEl('ul'),
                HtmlUtils.closeEl('li'),
            ]);
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
                '<span class="' + HtmlUtils.REPLACE + '">' + line + '</span>' +
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
        HtmlUtils: HtmlUtils,
        ModuleDatum: ModuleDatum,
    };
});
