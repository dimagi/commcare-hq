'use strict';
hqDefine("cloudcare/js/form_entry/form_ui", [
    'jquery',
    'knockout',
    'underscore',
    'DOMPurify/dist/purify.min',
    'hqwebapp/js/toggles',
    'es6!hqwebapp/js/bootstrap5_loader',
    'cloudcare/js/markdown',
    'cloudcare/js/utils',
    'cloudcare/js/form_entry/const',
    'cloudcare/js/form_entry/entries',
    'cloudcare/js/formplayer/users/models',
    'cloudcare/js/form_entry/utils',
    'jquery-tiny-pubsub/dist/ba-tiny-pubsub',       // $.pubsub
], function (
    $,
    ko,
    _,
    DOMPurify,
    toggles,
    bootstrap,
    markdown,
    cloudcareUtils,
    constants,
    entries,
    UsersModels,
    formEntryUtils
) {
    var groupNum = 0;

    _.delay(function () {
        ko.bindingHandlers.renderMarkdown = {
            update: function (element, valueAccessor) {
                var value = ko.unwrap(valueAccessor());
                value = markdown.render(value);
                $(element).html(value);
            },
        };
    });

    //if index is part of a repeat, return only the part beyond the deepest repeat
    function relativeIndex(ix) {
        var steps = ix.split(',');
        var deepestRepeat = -1,
            i;
        for (i = steps.length - 2; i >= 0; i--) {
            if (steps[i].indexOf(':') !== -1) {
                deepestRepeat = i;
                break;
            }
        }
        if (deepestRepeat === -1) {
            return ix;
        } else {
            var relIx = '-';
            for (i = deepestRepeat + 1; i < steps.length; i++) {
                relIx += steps[i] + (i < steps.length - 1 ? ',' : '');
            }
            return relIx;
        }
    }

    function getIx(o) {
        var ix = o.rel_ix();
        while (ix[0] === '-') {
            o = o.parent;
            if (!o || ko.utils.unwrapObservable(o.rel_ix) === undefined) {
                break;
            }
            if (o.rel_ix().split(',').slice(-1)[0].indexOf(':') !== -1) {
                ix = o.rel_ix() + ',' + ix.substring(1);
            }
        }
        return ix;
    }

    function getForIx(o, ix) {
        if (ko.utils.unwrapObservable(o.type) === 'question') {
            return (getIx(o) === ix ? o : null);
        } else {
            for (var i = 0; i < o.children().length; i++) {
                var result = getForIx(o.children()[i], ix);
                if (result) {
                    return result;
                }
            }
        }
    }

    function getQuestions(o) {
        if (ko.utils.unwrapObservable(o.type) === 'question') {
            return [o];
        } else {
            var qs = [];
            for (var i = 0; i < o.children().length; i++) {
                if (ko.utils.unwrapObservable(o.children()[i].type) === 'question') {
                    qs.push(o.children()[i]);
                } else {
                    qs = qs.concat(getQuestions(o.children()[i]));
                }
            }
            return qs;
        }
    }

    function getMatchingStyles(pattern, styleStr) {
        let matchingStyles = [];
        if (styleStr) {
            let styles = styleStr.split(' ');
            styles.forEach(function (style) {
                if ((pattern instanceof RegExp && style.match(pattern))
                    || (typeof pattern === "string" && pattern === style)) {
                    matchingStyles.push(style);
                }
            });
        }
        return matchingStyles;
    }

    function stylesContaining(pattern, style) {
        var styleStr = (style) ? ko.utils.unwrapObservable(style.raw) : null;
        return getMatchingStyles(pattern, styleStr);
    }

    function stylesContains(pattern, style) {
        return stylesContaining(pattern, style).length > 0;
    }

    function parseMeta(type, style) {
        var meta = {};

        if (type === "date") {
            meta.mindiff = style.before !== null ? +style.before : null;
            meta.maxdiff = style.after !== null ? +style.after : null;
        } else if (type === "int" || type === "float") {
            meta.unit = style.unit;
        } else if (type === 'str') {
            meta.autocomplete = (style.mode === 'autocomplete');
            meta.autocomplete_key = style["autocomplete-key"];
            meta.mask = style.mask;
            meta.prefix = style.prefix;
            meta.longtext = (style.raw === 'full');
        } else if (type === "multiselect") {
            if (style["as-select1"]) {
                meta.as_single = [];
                var vs = style["as-select1"].split(',');
                for (var i = 0; i < vs.length; i++) {
                    var k = +vs[i];
                    if (k !== 0) {
                        meta.as_single.push(k);
                    }
                }
            }
        }

        if (type === "select" || type === "multiselect") {
            meta.appearance = style.raw;
        }

        return meta;
    }

    function getParentForm(self) {
        let curr = self;
        while (curr.parent) {
            curr = curr.parent;
        }
        return curr;
    }

    function getNPerRowStyleFromRepeatStyle(styleStr) {
        const matchingPerRowRepeatStyles = getMatchingStyles(constants.PER_ROW_REPEAT_PATTERN, styleStr),
            perRowRepeatStyle = matchingPerRowRepeatStyles.length ? matchingPerRowRepeatStyles[0] : null;
        if (perRowRepeatStyle) {
            const integerPart = perRowRepeatStyle.split('-')[0];
            return integerPart + constants.PER_ROW;
        } else {
            return '';
        }
    }

    function processNPerRowRepeatStyle(json) {
        if (stylesContains(constants.PER_ROW_REPEAT_PATTERN, json.style)) {
            const elementNPerRowStyle = getNPerRowStyleFromRepeatStyle(json.style.raw);
            for (let groupChild of json.children) {
                // Detects configured repeat groups within the form. If a repeat group has a 'repeat-count' configured,
                // the Formplayer response designates the key 'type' as 'sub-group' and 'repeatable' as 'true'.
                if ((groupChild.type === constants.GROUP_TYPE && groupChild.repeatable === "true")) {
                    if (_.has(groupChild, 'style') && groupChild.style && groupChild.style.raw) {
                        groupChild.style.raw = groupChild.style.raw.concat(" ", elementNPerRowStyle);
                    } else {
                        groupChild.style = {'raw': elementNPerRowStyle};
                    }
                }
            }
        }
    }

    /**
     * Base abstract prototype for Repeat, Group, GroupedElementTileRow, and Form. Adds methods to
     * objects that contain a children array for rendering nested questions.
     * @param {Object} json - The JSON returned from touchforms to represent the container
     */
    function Container(json) {
        var self = this;
        self.pubsub = new ko.subscribable();
        self.fromJS(json);

        /**
         * Used in KO template to determine what template to use for a child
         * @param {Object} child - The child object to be rendered, either Group, Repeat, or Question
         */
        self.childTemplate = function (child) {
            return child.type() + '-fullform-ko-template';
        };

        self.hasError = ko.computed(function () {
            return _.find(self.children(), function (child) {
                return child.hasError();
            });
        });
    }

    /**
     * Reconciles the JSON representation of a Container (Group, Repeat, Form) and renders it into
     * a knockout representation.
     * @param {Object} json - The JSON returned from touchforms to represent a Container
     */
    Container.prototype.fromJS = function (json) {
        var self = this;

        if (!json.type) {
            Container.groupElements(json);
        }

        var mapping = {
            caption: {
                update: function (options) {
                    if (self.hideCaption) {
                        return null;
                    }
                    return options.data ? DOMPurify.sanitize(options.data.replace(/\n/g, '<br/>')) : null;
                },
            },
            caption_markdown: {
                update: function (options) {
                    return options.data ? markdown.render(options.data) : null;
                },
            },
            children: {
                create: function (options) {
                    if (options.data.type === constants.GROUPED_ELEMENT_TILE_ROW_TYPE) {
                        return new GroupedElementTileRow(options.data, self);
                    } else if (options.data.type === constants.QUESTION_TYPE) {
                        return new Question(options.data, self);
                    } else if (options.data.type === constants.GROUP_TYPE) {
                        return new Group(options.data, self);
                    } else {
                        console.error('Could not find question type of ' + options.data.type);
                    }
                },
                update: function (options) {
                    if (options.target.pendingAnswer &&
                            options.target.pendingAnswer() !== constants.NO_PENDING_ANSWER) {
                        // There is a request in progress, check if the answer has changed since the request
                        // was made. For file questions, it is most unlikely that the answer will change while the request
                        // is in progress, so we just ignore the value.
                        if (options.target.entry.templateType === "file"
                            || options.target.entry.templateType === "signature"
                            || formEntryUtils.answersEqual(options.data.answer, options.target.pendingAnswer())
                        ) {
                            // We can now mark it as not dirty
                            options.target.pendingAnswer(constants.NO_PENDING_ANSWER);
                        } else {
                            // still dirty - most likely edited by the user while the request was going
                            // Keep answer the same as the pending one to avoid overwriting the user's changes
                            options.data.answer = _.clone(options.target.pendingAnswer());
                        }
                    }

                    // Do not update the answer if there is a server error on that question
                    if (ko.utils.unwrapObservable(options.target.serverError)) {
                        options.data.answer = _.clone(options.target.answer());
                    }
                    if (options.target.choices && _.isEqual(options.target.choices(), options.data.choices)) {
                        // replacing the full choice list if it has a few thousand items
                        // is actually quite expensive and can freeze the page for seconds.
                        // at the very least we can skip entirely when there's no change.
                        delete options.data.choices;
                    }
                    return options.target;
                },
                key: function (data) {
                    const uuid = ko.utils.unwrapObservable(data.uuid);
                    if (uuid) {
                        return uuid;
                    }
                    const exists = ko.utils.unwrapObservable(data.exists);
                    const ix = ko.utils.unwrapObservable(data.ix);
                    if (exists && exists === 'false') {
                        // this is a add group button. replace last part with d
                        const lastIdx = ix.lastIndexOf('_');
                        return lastIdx === -1 ? ix : ix.slice(0, lastIdx) + '_d';
                    }
                    return ix;
                },
            },
        };
        ko.mapping.fromJS(json, mapping, self);
    };

    /**
     * Calculates background color for nested Group and Repeat headers.
     * Recursively determines nesting level (considering only Group and Repeat),
     * starting at 0 for the Form level and cycling colors for each level.
     *
     * @returns {string} - Background color for the header's nesting level.
     */
    Container.prototype.headerBackgroundColor = function () {
        let currentNode = this;
        let nestedDepthCount = 0;
        while (currentNode.parent) {
            if (currentNode.type() === constants.GROUP_TYPE && currentNode.collapsible) {
                nestedDepthCount += 1;
            }
            currentNode = currentNode.parent;
        }

        // Colors are ordered from darkest to lightest with the darkest color for the highest level.
        // Colors are based on shades of @cc-brand-mid.
        // shade(#004EBC, 20%) #003e96
        // shade(#004EBC, 40%) #002f71
        const repeatColor = ["#002f71", "#003e96", "#004EBC"];
        const repeatColorCount = repeatColor.length;
        const index = (nestedDepthCount - 1) % repeatColorCount;

        return repeatColor[index];
    };

    /**
     * Recursively groups sequential "Question" or "Group" items in a nested JSON structure.
     *
     * This function takes a JSON object as input and searches for sequential "Question" or "Group"
     * items within the 'children' arrays of the input and its nested "Group" objects.
     * It groups the sequential "Question" items and "Group"
     * items into "GroupedElementTileRow" objects while maintaining the original structure of the JSON.
     *
     * @param {Object} json - The JSON object to process, containing 'children' arrays.
     * @returns {Object} - A new JSON object with sequential "Question" items and sequential
     * "Group" items grouped into "GroupedElementTileRow".
     */
    Container.groupElements = function (json) {
        if (!json || !json.children || !Array.isArray(json.children)) {
            return json;
        }

        const newChildren = [];
        let currentGroup = null;
        let usedWidth = 0;

        function addToCurrentGroup(child) {
            if (!currentGroup) {
                currentGroup = {
                    type: constants.GROUPED_ELEMENT_TILE_ROW_TYPE,
                    children: [],
                    ix: null,
                };
                newChildren.push(currentGroup);
            }
            currentGroup.children.push(child);
        }

        function resetCurrentGroup() {
            if (currentGroup) {
                const ixValuesWithParentheses = currentGroup.children.map(child => `(${child.ix})`);
                currentGroup.ix = ixValuesWithParentheses.join(",");
            }
            currentGroup = null;
            usedWidth = 0;
        }

        if (json.type === constants.GROUP_TYPE) {
            processNPerRowRepeatStyle(json);
        }

        for (let child of json.children) {
            if (child.type === constants.QUESTION_TYPE || child.type === constants.GROUP_TYPE) {
                const elementTileWidth = GroupedElementTileRow.calculateElementWidth(child.style);
                usedWidth += elementTileWidth;
                if (usedWidth > constants.GRID_COLUMNS) {
                    resetCurrentGroup();
                    usedWidth += elementTileWidth;
                }

                if (child.type === constants.GROUP_TYPE) {
                    child = Container.groupElements(child);
                }

                addToCurrentGroup(child);
            } else {
                newChildren.push(child);
                resetCurrentGroup();
            }
        }
        resetCurrentGroup();
        json.children = newChildren;
        return json;
    };

    /**
     * Remove all nodes from the root that share the same prefix in the ix as the deleted repeat
     * group. Changes the rootNode in place.
     *
     * @param rootNode
     * @param deletedGroupIx
     */
    function removeSiblingsOfRepeatGroup(rootNode, deletedGroupIx) {
        const ixParts = deletedGroupIx.split(",");
        let parentOfDeletedGroup = rootNode;
        for (let i = 0; i < ixParts.length - 1; i++) {
            parentOfDeletedGroup = parentOfDeletedGroup.children.find(c => c.ix.endsWith(ixParts[i]));
        }
        const siblingsOfDeletedGroup = parentOfDeletedGroup.children;

        const getIxPrefix = (ix) => ix.substr(0, ix.lastIndexOf("_") + 1);
        const getIxNestedPosition = (ix) => ix.substr(ix.lastIndexOf("_") + 1, ix.lastIndexOf("_") + 2);

        const deletedGroupIxPrefix = getIxPrefix(deletedGroupIx);
        parentOfDeletedGroup.children = siblingsOfDeletedGroup.filter(function (c) {
            return !c.ix.startsWith(deletedGroupIxPrefix);
        });

        // Preserve the 'collapsed' state of the group upon rerendering.
        // This is done by decrementing the ix of siblings that come after the deleted group.
        let collapsedIx = JSON.parse(sessionStorage.getItem('collapsedIx')) || [];
        collapsedIx = collapsedIx
            .filter(ix => !ix.startsWith(deletedGroupIx) && ix !== deletedGroupIx);
        collapsedIx = collapsedIx.map(ix => {
            if (ix.startsWith(deletedGroupIxPrefix)) {
                let IxNestedPosition = getIxNestedPosition(ix);
                if (IxNestedPosition > getIxNestedPosition(deletedGroupIx)) {
                    IxNestedPosition--;
                }
                return getIxPrefix(ix) + IxNestedPosition;
            }
            return ix;
        });
        sessionStorage.setItem('collapsedIx', JSON.stringify(collapsedIx));

    }

    /**
     * Represents the entire form. There is only one of these on a page.
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     */
    function Form(json) {
        var self = this;
        self.displayOptions = json.displayOptions || {};
        json.children = json.tree;
        delete json.tree;
        Container.call(self, json);
        self.blockSubmit = ko.observable(false);
        self.hasSubmitAttempted = ko.observable(false);
        self.isSubmitting = ko.observable(false);
        self.isAnchoredSubmitStyle = toggles.toggleEnabled('WEB_APPS_ANCHORED_SUBMIT');

        self.currentIndex = ko.observable("0");
        self.atLastIndex = ko.observable(false);
        self.atFirstIndex = ko.observable(true);
        self.shouldAutoSubmit = json.shouldAutoSubmit;

        var _updateIndexCallback = function (ix, isAtFirstIndex, isAtLastIndex) {
            self.currentIndex(ix.toString());
            self.atFirstIndex(isAtFirstIndex);
            self.atLastIndex(isAtLastIndex);
        };

        self.showInFormNavigation = ko.computed(function () {
            return self.displayOptions.oneQuestionPerScreen !== undefined
            && self.displayOptions.oneQuestionPerScreen() === true;
        });

        self.isCurrentRequiredSatisfied = ko.computed(function () {
            if (!self.showInFormNavigation()) {
                return true;
            }

            let questions = getQuestions(self);
            return _.every(questions, function (q) {
                return (q.answer() === constants.NO_ANSWER && !q.required()) || q.answer() !== null;
            });
        });
        self.isCurrentRequiredSatisfied.subscribe(function (isSatisfied) {
            if (isSatisfied) {
                self.forceRequiredVisible(false);
            }
        });

        self.enableNextButton = ko.computed(function () {
            if (!self.showInFormNavigation()) {
                return false;
            }

            let questions = getQuestions(self);
            var allValidAndNotPending = _.every(questions, function (q) {
                return q.isValid() && !q.pendingAnswer();
            });
            return allValidAndNotPending
                && self.showInFormNavigation()
                && self.isCurrentRequiredSatisfied()
                && !self.atLastIndex();
        });

        self.enablePreviousButton = ko.computed(function () {
            if (!self.showInFormNavigation()) {
                return false;
            }
            return self.currentIndex() !== "0" && self.currentIndex() !== "-1" && !self.atFirstIndex();
        });

        self.erroredLabels = ko.computed(function () {
            var questions = getQuestions(self);
            var erroredLabels = {};
            for (var i = 0; i < questions.length; i++) {
                if (questions[i].isLabel && !questions[i].isValid()) {
                    erroredLabels[getIx(questions[i])] = "OK";
                }
            }
            return erroredLabels;
        });

        self.erroredQuestions = ko.computed(function () {
            if (!self.hasSubmitAttempted()) {
                return [];
            }

            var questions = getQuestions(self);
            var qs = [];
            for (var i = 0; i < questions.length; i++) {
                // eslint-disable-next-line
                if (questions[i].error() != null || questions[i].serverError() != null
                            || (questions[i].required() && questions[i].answer() === null)) {
                    qs.push(questions[i]);
                }
            }
            return qs;
        });

        self.currentJumpPoint = null;
        self.jumpToErrors = function () {
            var erroredQuestions = self.erroredQuestions();
            for (var i = erroredQuestions.length - 1; i >= 0; i--) {
                if (!self.currentJumpPoint || !erroredQuestions.includes(self.currentJumpPoint)) {
                    self.currentJumpPoint = erroredQuestions[0];
                    break;
                }
                if (self.currentJumpPoint.entry.entryId === erroredQuestions[i].entry.entryId) {
                    if (i === erroredQuestions.length - 1) {
                        self.currentJumpPoint = erroredQuestions[0];
                    } else {
                        self.currentJumpPoint = erroredQuestions[i + 1];
                    }
                    break;
                }
            }
            self.currentJumpPoint.navigateTo();
        };

        self.enableSubmitButton = ko.computed(function () {
            return !self.isSubmitting() && self.erroredQuestions().length === 0;
        });

        self.getSubmitTranslation = function () {
            var translations = self.translations;
            if (translations) {
                const result = Object.entries(translations).find(([k]) => k.includes("submit_label"));
                if (result) {
                    const key = result[0];
                    return ko.toJS(translations[key]);
                }
            }
            return gettext("Submit");
        };

        self.submitText = ko.computed(function () {
            if (self.isSubmitting()) {
                return gettext('Submitting...');
            }
            return self.getSubmitTranslation();
        });

        self.forceRequiredVisible = ko.observable(false);

        self.showRequiredNotice = ko.computed(function () {
            return !self.isCurrentRequiredSatisfied() && self.forceRequiredVisible();
        });

        self.clickedNextOnRequired = function () {
            self.forceRequiredVisible(true);
        };

        self.enableForceNextButton = ko.computed(function () {
            return !self.isCurrentRequiredSatisfied() && !self.enableNextButton();
        });

        self.disableNextButton = ko.computed(function () {
            return !self.enableNextButton() && !self.enableForceNextButton();
        });

        self.showSubmitButton = ko.computed(function () {
            return !self.showInFormNavigation() && !self.shouldAutoSubmit;
        });

        self.submitForm = function () {
            $(document).onvisibilitychange = () => {
                if (document.visibilityState === "hidden") {
                    self.showSubmitButton = false;
                }
            };
            self.hasSubmitAttempted(true);
            $.publish('formplayer.' + constants.SUBMIT, self);
        };

        self.nextQuestion = function () {
            $.publish('formplayer.' + constants.NEXT_QUESTION, {
                callback: _updateIndexCallback,
                title: self.title(),
            });
        };

        self.prevQuestion = function () {
            $.publish('formplayer.' + constants.PREV_QUESTION, {
                callback: _updateIndexCallback,
                title: self.title(),
            });
        };

        self.getTranslation = function (translationKey, defaultTranslation) {
            // Find the root level element which contains the translations.
            var translations = self.translations;

            if (translations) {
                var translationText = ko.toJS(translations[translationKey]);
                if (translationText) {
                    return translationText;
                }
            }
            return defaultTranslation;
        };

        self.afterRender = function () {
            $(document).on("click", ".help-text-trigger", function (event) {
                event.preventDefault();
                var container = $(event.currentTarget).closest(".caption");
                bootstrap.Modal.getOrCreateInstance(container.find(".modal")).show();
            });

            $(document).on("click", ".unsupported-question-type-trigger", function (event) {
                var container = $(event.currentTarget).closest(".widget");
                bootstrap.Modal.getOrCreateInstance(container.find(".modal")).show();
            });
        };

        $.unsubscribe('session');
        $.subscribe('session.reconcile', function (e, response, element, options) {
            // TODO where does response status parsing belong?
            if (response.status === 'validation-error') {
                if (response.type === 'required') {
                    element.serverError(gettext('An answer is required'));
                } else if (response.type === 'constraint') {
                    element.serverError(response.reason || gettext('This answer is outside the allowed range.'));
                }
                element.pendingAnswer(constants.NO_PENDING_ANSWER);
            } else {
                const allChildren = response.tree;
                delete response.tree;

                if (options) {
                    // deletedGroup is only set for responses from delete-repeat.
                    // because ko.mapping does not like reassigning keys we need to remove all repeat group siblings and
                    // add them back in to force proper refresh. Setting response.children to [] would also work but was
                    // quite slow for larger forms.
                    // self.fromJS makes changes to the response. So create a copy first.
                    response.children = JSON.parse(JSON.stringify(allChildren));
                    if (options.deletedGroup) {
                        removeSiblingsOfRepeatGroup(response, options.deletedGroup);
                    }
                    self.fromJS(response);
                }

                if (element.serverError) {
                    element.serverError(null);
                }

                const inputControl = [constants.CONTROL_IMAGE_CHOOSE, constants.CONTROL_LABEL,
                    constants.CONTROL_AUDIO_CAPTURE, constants.CONTROL_VIDEO_CAPTURE];

                let findChildAndSetFilename = function (children) {
                    for (let child of children) {
                        if (child.children && child.children.length > 0) {
                            findChildAndSetFilename(child.children);
                        } else if (inputControl.includes(child.control) && element.binding() === child.binding &&
                            element.ix() === child.ix && element.answer()) {
                            child.filename = element.answer();
                            return;
                        }
                    }
                };
                if (_.has(element, 'binding') && _.has(element, 'ix') && !_.isEmpty(allChildren)) {
                    findChildAndSetFilename(allChildren);
                }

                response.children = allChildren;
                self.fromJS(response);
            }
        });

        $.subscribe('session.block', function (e, block) {
            $('#webforms input, #webforms textarea').prop('disabled', block === constants.BLOCK_ALL);
            self.blockSubmit(block === constants.BLOCK_ALL || block === constants.BLOCK_SUBMIT);
        });
    }
    Form.prototype = Object.create(Container.prototype);
    Form.prototype.constructor = Container;

    /**
     * Represents a group of GroupedElementTileRow which contains Question or Group objects.
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
     */
    function Group(json, parent) {
        var self = this;
        self.parent = parent;
        Container.call(self, json);

        self.isDummy = ko.observable(self.exists() === "false");
        self.addChoice = ko.observable(json['add-choice']);

        self.groupId = groupNum++;
        self.rel_ix = ko.pureComputed(() => relativeIndex(self.ix()));
        if (Object.hasOwn(self, 'delete')) {
            self.showDelete = self.delete();
        } else {
            self.showDelete = false;
        }
        const isRepeatable = ko.utils.unwrapObservable(self.repeatable) === "true";
        let parentForm = getParentForm(self);
        let oneQuestionPerScreen = parentForm.displayOptions.oneQuestionPerScreen !== undefined && parentForm.displayOptions.oneQuestionPerScreen();

        self.hasNoPendingAnswer = ko.pureComputed(function () {
            return !self.parent.hasAnyNestedQuestionWithPendingAnswer();
        });

        // Header and captions
        self.showHeader = oneQuestionPerScreen || ko.utils.unwrapObservable(self.caption) || ko.utils.unwrapObservable(self.caption_markdown) || self.showDelete;

        if (_.has(json, 'domain_meta') && _.has(json, 'style')) {
            self.domain_meta = parseMeta(json.datatype, json.style);
        }

        self.focusNewRepeat = function () {
            var repeat = $('.repetition');
            if (repeat) {
                repeat.trigger('focus');
            }
        };

        let collapsedIx = JSON.parse(sessionStorage.getItem('collapsedIx')) || [];
        var styles = _.has(json, 'style') && json.style && json.style.raw ? json.style.raw.split(/\s+/) : [];
        self.collapsible = (_.contains(styles, constants.COLLAPSIBLE) || isRepeatable) && self.showHeader;
        self.groupBorder = _.contains(styles, constants.GROUP_BORDER);
        self.showChildren = ko.observable(!self.collapsible || _.contains(styles, constants.COLLAPSIBLE_OPEN) || (isRepeatable && !collapsedIx.includes(self.rel_ix())));
        self.toggleChildren = function () {
            if (self.collapsible) {
                if (self.showChildren()) {
                    let collapsedIx = JSON.parse(sessionStorage.getItem('collapsedIx')) || [];
                    collapsedIx.push(self.rel_ix());
                    sessionStorage.setItem('collapsedIx', JSON.stringify(collapsedIx));
                    self.showChildren(false);
                } else {
                    let collapsedIx = JSON.parse(sessionStorage.getItem('collapsedIx')) || [];
                    collapsedIx = collapsedIx.filter(e => e !== self.rel_ix());
                    sessionStorage.setItem('collapsedIx', JSON.stringify(collapsedIx));
                    self.showChildren(true);
                }
            }
        };

        self.captionId = function () {
            return "group_".concat(self.groupId).concat("_caption");
        };

        self.keyPressAction = function (data, event) {
            // Toggle children on Enter or Space.
            if (event.keyCode === 13 || event.keyCode === 32) {
                this.toggleChildren(data, event);
            }
        };
        self.childrenRequired = ko.computed(function () {
            return _.find(self.children(), function (child) {
                return child.required() || child.childrenRequired && child.childrenRequired();
            });
        });

        self.newRepeat = function () {
            $.publish('formplayer.' + constants.NEW_REPEAT, self);
            $.publish('formplayer.' + constants.DIRTY);
            $('.add').trigger('blur');
        };

        self.deleteRepeat = function () {
            $.publish('formplayer.' + constants.DELETE_REPEAT, self);
            $.publish('formplayer.' + constants.DIRTY);
        };

        self.hasAnyNestedQuestions = function () {
            return self.isDummy() || _.any(self.children(), function (d) {
                if (d.type() === constants.GROUPED_ELEMENT_TILE_ROW_TYPE) {
                    return d.hasAnyNestedQuestions();
                }
            });
        };

        self.hasAnyNestedQuestionWithPendingAnswer = ko.pureComputed(function () {
            return _.any(self.children(), function (d) {
                if (d.type() === constants.GROUPED_ELEMENT_TILE_ROW_TYPE) {
                    return d.hasAnyNestedQuestionWithPendingAnswer();
                }
            });
        });

        self.isVisibleGroup = function () {
            const hasChildren = self.children().length !== 0;
            const hasLabel = !!ko.utils.unwrapObservable(self.caption_markdown) || !!self.caption();
            return hasChildren && hasLabel;
        };

        self.headerBackgroundColor = function () {
            if (!self.collapsible) {
                return '';
            }
            return Container.prototype.headerBackgroundColor.call(self);
        };

        let columnWidth = GroupedElementTileRow.calculateElementWidth(this.style);
        this.elementTile = `col-md-${columnWidth}`;
    }

    Group.prototype = Object.create(Container.prototype);
    Group.prototype.constructor = Container;

    /**
     * Represents a group of Questions, Group, or Repeat. Elements are grouped such that all elements are
     * contained in the same row.
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
     */
    function GroupedElementTileRow(json, parent) {
        var self = this;
        self.parent = parent;
        Container.call(self, json);

        self.hasAnyNestedQuestionWithPendingAnswer = ko.pureComputed(function () {
            return _.any(self.children(), function (d) {
                if (d.type() === constants.QUESTION_TYPE) {
                    return d.pendingAnswer();
                } else if (d.type() === constants.GROUP_TYPE) {
                    return d.hasAnyNestedQuestionWithPendingAnswer();
                }
                return false;
            });
        });

        self.hasAnyNestedQuestions = function () {
            return _.any(self.children(), function (d) {
                if (d.type() === constants.QUESTION_TYPE) {
                    return true;
                } else if (d.type() === constants.GROUP_TYPE) {
                    return d.hasAnyNestedQuestions();
                }
            });
        };

        self.required = ko.observable(0);
        self.childrenRequired = ko.computed(function () {
            return _.find(self.children(), function (child) {
                return (child.required && child.required() || child.childrenRequired && child.childrenRequired());
            });
        });
    }
    GroupedElementTileRow.prototype = Object.create(Container.prototype);
    GroupedElementTileRow.prototype.constructor = Container;

    /**
     * Matches "<n>-per-row" style attributes. If a match if found, it calculates the column width
     * based on Bootstrap's 12 column grid system and returns the column width.
     * @param {Object} style - the appearance attributes
     */
    GroupedElementTileRow.calculateElementWidth = function (style) {
        const styleStr = (style) ? ko.utils.unwrapObservable(style.raw) : null;
        const matchingPerRowStyles = getMatchingStyles(constants.PER_ROW_PATTERN, styleStr);
        const perRowStyle = matchingPerRowStyles.length === 0 ? null : matchingPerRowStyles[0];
        const itemsPerRow = perRowStyle !== null ? parseInt(perRowStyle.split("-")[0], 10) : null;

        return itemsPerRow !== null ? Math.round(constants.GRID_COLUMNS / itemsPerRow) : constants.GRID_COLUMNS;
    };

    /**
     * Represents a Question. A Question contains an Entry which is the widget that is displayed for that question
     * type.
     * child questions to be rendered
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
     */
    function Question(json, parent) {
        var self = this;
        self.fromJS(json);
        self.parent = parent;
        // Grab the containing pubsub so questions can interact with other questions on the same form.
        const container = formEntryUtils.getBroadcastContainer(self);
        self.broadcastPubSub = (container) ? container.pubsub : new ko.subscribable();
        self.error = ko.observable(null);
        self.serverError = ko.observable(null);
        self.rel_ix = ko.observable(relativeIndex(self.ix()));
        if (_.has(json, 'domain_meta') && _.has(json, 'style')) {
            self.domain_meta = parseMeta(json.datatype, json.style);
        }
        self.throttle = 200;
        // If the question has ever been answered, set this to true.
        self.hasAnswered = false;

        // Media questions use a Deferred object that is resolved on successful Formplayer processing
        self.formplayerMediaRequest = null;

        // pendingAnswer is a copy of an answer being submitted, so that we know not to reconcile a new answer
        // until the question has received a response from the server.
        self.pendingAnswer = ko.observable(constants.NO_PENDING_ANSWER);
        self.pendingAnswer.subscribe(function () { self.hasAnswered = true; });
        self.dirty = ko.computed(function () {
            return self.pendingAnswer() !== constants.NO_PENDING_ANSWER;
        });
        self.hasError = ko.computed(function () {
            return (self.error() || self.serverError()) && !self.dirty();
        });

        self.isButton = self.datatype() === 'select' && self.stylesContains(constants.BUTTON_SELECT);
        self.isLabel = self.datatype() === 'info';
        self.hasLabelContent = ko.computed(function () {
            return !self.isButton && (
                ko.utils.unwrapObservable(self.caption)
                || ko.utils.unwrapObservable(self.caption_markdown)
                || ko.utils.unwrapObservable(self.help)
                || ko.utils.unwrapObservable(self.hint)
                || ko.utils.unwrapObservable(self.required)
            );
        });
        self.setWidths(self.hasLabelContent());

        self.form = function () {
            var parent = self.parent;
            while (parent.type && parent.type() !== null) {
                parent = parent.parent;
            }
            return parent;
        };

        self.isValid = function () {
            return self.error() === null && self.serverError() === null;
        };

        self.entry = entries.getEntry(self);
        self.entryTemplate = function () {
            return self.entry.templateType + '-entry-ko-template';
        };
        self.afterRender = function () { self.entry.afterRender(); };

        self.ixInfo = function (o) {
            var fullIx = getIx(o);
            return o.rel_ix + (o.rel_ix !== fullIx ? ' :: ' + fullIx : '');
        };

        self.triggerAnswer = function () {
            self.pendingAnswer(_.clone(self.answer()));
            publishAnswerEvent();
        };
        var publishAnswerEvent = _.throttle(function () {
            $.publish('formplayer.' + constants.DIRTY);
            $.publish('formplayer.' + constants.ANSWER, self);
        }, self.throttle);
        self.onchange = self.triggerAnswer;

        self.onClear = _.throttle(function () {
            $.publish('formplayer.' + constants.CLEAR_ANSWER, self);
        }, self.throttle);

        self.mediaSrc = function (resourceType) {
            if (!resourceType || !_.isFunction(formEntryUtils.resourceMap)) { return ''; }
            return formEntryUtils.resourceMap(resourceType);
        };

        self.navigateTo = function () {
            // toggle nested collapsible Groups
            var hasParent = self.parent !== undefined;
            var currentNode = self;
            while (hasParent) {
                hasParent = currentNode.parent !== undefined;
                var parent = currentNode.parent;
                if (parent !== undefined && parent.collapsible !== undefined && !parent.showChildren()) {
                    parent.toggleChildren();
                }
                currentNode = parent;
            }
            var el = $("#" + self.entry.entryId + "-label");
            const scrollContainer = $('#content-plus-version-info-container');
            scrollContainer.animate({
                scrollTop: scrollContainer.scrollTop() + $(el).offset().top - 80,
            });
            self.form().currentJumpPoint = self;
            el.fadeOut(200).fadeIn(200).fadeOut(200).fadeIn(200);
        };
    }

    /**
     * Reconciles the JSON representation of a Question and renders it into
     * a knockout representation.
     * @param {Object} json - The JSON returned from touchforms to represent a Question
     */
    Question.prototype.fromJS = function (json) {
        var self = this;
        var mapping = {
            caption: {
                update: function (options) {
                    return options.data ? DOMPurify.sanitize(options.data.replace(/\n/g, '<br/>')) : null;
                },
            },
            caption_markdown: {
                update: function (options) {
                    return options.data ? markdown.render(options.data) : null;
                },
            },
            help: {
                update: function (options) {
                    return options.data ? markdown.render(options.data) : null;
                },
            },
        };

        ko.mapping.fromJS(json, mapping, self);
    };

    /**
     * Returns a list of style strings that match the given pattern.
     * If a regex is provided, returns regex matches. If a string is provided
     * an exact match is returned.
     * @param {Object} pattern - the regex or string used to find matching styles.
     */
    Question.prototype.stylesContaining = function (pattern) {
        var self = this;
        return stylesContaining(pattern, self.style);
    };

    /**
     * Returns a boolean of whether the styles contain a pattern.
     * @param {Object} pattern - the regex or string used to find matching styles.
     */
    Question.prototype.stylesContains = function (pattern) {
        let _self = this;
        return stylesContains(pattern, _self.style);
    };

    Question.prototype.setWidths = function (hasLabel) {
        const self = this;
        const columnWidth = GroupedElementTileRow.calculateElementWidth(self.style);

        if (self.stylesContains(constants.PER_ROW_PATTERN)) {
            self.controlWidth = "";
            self.labelWidth = "";
            self.questionTileWidth = `col-md-${columnWidth}`;
        } else {
            if (self.isLabel) {
                self.controlWidth = "";
                self.labelWidth = constants.FULL_WIDTH;
            } else {
                self.controlWidth = constants.CONTROL_WIDTH;
                self.labelWidth = constants.LABEL_WIDTH;
            }
            self.questionTileWidth = constants.FULL_WIDTH;
            if (!hasLabel && !self.isLabel) {
                self.controlWidth += ' ' + constants.LABEL_OFFSET;
            }
        }

        if (self.stylesContains(constants.SHORT)) {
            self.controlWidth = constants.SHORT_WIDTH;
        } else if (self.stylesContains(constants.MEDIUM)) {
            self.controlWidth = constants.MEDIUM_WIDTH;
        }
    };

    return {
        getIx: getIx,
        getForIx: getForIx,
        Form: function (json) {
            return new Form(json);
        },
        Question: function (json, parent) {
            return new Question(json, parent);
        },
        removeSiblingsOfRepeatGroup: removeSiblingsOfRepeatGroup,
    };
});
