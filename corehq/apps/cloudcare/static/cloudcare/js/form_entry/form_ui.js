/* global DOMPurify */
hqDefine("cloudcare/js/form_entry/form_ui", function () {
    var markdown = hqImport("cloudcare/js/markdown"),
        constants = hqImport("cloudcare/js/form_entry/const"),
        entries = hqImport("cloudcare/js/form_entry/entries"),
        formEntryUtils = hqImport("cloudcare/js/form_entry/utils");
    var groupNum = 0;

    _.delay(function () {
        ko.bindingHandlers.renderMarkdown = {
            update: function (element, valueAccessor) {
                var value = ko.unwrap(valueAccessor());
                value = markdown.render(value || '');
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

    /**
     * Base abstract prototype for Repeat, Group, GroupedQuestionTileRow, and Form. Adds methods to
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
            return ko.utils.unwrapObservable(child.type) + '-fullform-ko-template';
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
            Container.groupQuestions(json);
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
                    if (options.data.type === constants.GROUPED_QUESTION_TILE_ROW_TYPE) {
                        return new GroupedQuestionTileRow(options.data, self);
                    } else if (options.data.type === constants.QUESTION_TYPE) {
                        return new Question(options.data, self);
                    } else if (options.data.type === constants.GROUP_TYPE) {
                        return new Group(options.data, self);
                    } else if (options.data.type === constants.REPEAT_TYPE) {
                        return new Repeat(options.data, self);
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
                        if (options.target.entry.templateType === "file" || formEntryUtils.answersEqual(options.data.answer, options.target.pendingAnswer())) {
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
                    return ko.utils.unwrapObservable(data.uuid) || ko.utils.unwrapObservable(data.ix);
                },
            },
        };
        ko.mapping.fromJS(json, mapping, self);
    };

    /**
     * Recursively groups sequential "question" items in a nested JSON structure.
     *
     * This function takes a JSON object as input and searches for sequential "question"
     * items within the 'children' arrays of the input and its nested 'group' objects.
     * It groups these sequential "question" items into "GroupedQuestionTileRow" objects while
     * maintaining the original structure of the JSON.
     *
     * @param {Object} json - The JSON object to process, containing 'children' arrays.
     * @returns {Object} - A new JSON object with sequential "question" items grouped into "GroupedQuestionTileRow".
     */
    Container.groupQuestions = function (json) {
        if (!json || !json.children || !Array.isArray(json.children)) {
            return json;
        }

        const newChildren = [];
        let currentGroup = null;
        let usedWidth = 0;

        function addToCurrentGroup(child) {
            if (!currentGroup) {
                currentGroup = {
                    type: constants.GROUPED_QUESTION_TILE_ROW_TYPE,
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

        for (let child of json.children) {
            if (child.type === constants.QUESTION_TYPE) {
                const questionTileWidth = Question.calculateColumnWidthForPerRowStyle(child.style);
                usedWidth += questionTileWidth;
                if (usedWidth > constants.GRID_COLUMNS) {
                    resetCurrentGroup();
                    usedWidth += questionTileWidth;
                }
                addToCurrentGroup(child);
            } else if (child.type === constants.GROUP_TYPE || child.type === constants.REPEAT_TYPE) {
                const newGroup = Container.groupQuestions(child);
                newChildren.push(newGroup);
                resetCurrentGroup();
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
        self.submitClass = constants.LABEL_OFFSET + ' ' + constants.CONTROL_WIDTH;

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

        self.submitText = ko.computed(function () {
            if (self.isSubmitting()) {
                return gettext('Submitting...');
            }
            return gettext('Submit');
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

        self.afterRender = function () {
            $(document).on("click", ".help-text-trigger", function (event) {
                event.preventDefault();
                var container = $(event.currentTarget).closest(".caption");
                container.find(".modal").modal('show');
            });

            $(document).on("click", ".unsupported-question-type-trigger", function (event) {
                var container = $(event.currentTarget).closest(".widget");
                container.find(".modal").modal('show');
            });
        };

        $.unsubscribe('session');
        $.subscribe('session.reconcile', function (e, response, element) {
            // TODO where does response status parsing belong?
            if (response.status === 'validation-error') {
                if (response.type === 'required') {
                    element.serverError(gettext('An answer is required'));
                } else if (response.type === 'constraint') {
                    element.serverError(response.reason || gettext('This answer is outside the allowed range.'));
                }
                element.pendingAnswer(constants.NO_PENDING_ANSWER);
            } else {
                response.children = response.tree;
                delete response.tree;
                if (element.serverError) { element.serverError(null); }
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
     * Represents a group of GroupedQuestionTileRow which contains questions.
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
     */
    function Group(json, parent) {
        var self = this;
        self.parent = parent;
        Container.call(self, json);

        self.groupId = groupNum++;
        self.rel_ix = ko.observable(relativeIndex(self.ix()));
        self.isRepetition = parent instanceof Repeat;
        let parentForm = getParentForm(self);
        let oneQuestionPerScreen = parentForm.displayOptions.oneQuestionPerScreen !== undefined && parentForm.displayOptions.oneQuestionPerScreen();

        if (!oneQuestionPerScreen && self.isRepetition) {
            self.caption(null);
            self.hideCaption = true;
        }
        if (_.has(json, 'domain_meta') && _.has(json, 'style')) {
            self.domain_meta = parseMeta(json.datatype, json.style);
        }

        self.focusNewRepeat = function () {
            var repeat = $('.repetition');
            if (repeat) {
                repeat.trigger('focus');
            }
        };

        var styles = _.has(json, 'style') && json.style && json.style.raw ? json.style.raw.split(/\s+/) : [];
        self.collapsible = _.contains(styles, constants.COLLAPSIBLE);
        self.showChildren = ko.observable(!self.collapsible || _.contains(styles, constants.COLLAPSIBLE_OPEN));
        self.toggleChildren = function () {
            if (self.collapsible) {
                if (self.showChildren()) {
                    self.showChildren(false);
                } else {
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

        if (self.isRepetition) {
            // If the group is part of a repetition the index can change if the user adds or deletes
            // repeat groups.
            self.ix.subscribe(function () {
                self.rel_ix(relativeIndex(self.ix()));
            });
        }

        self.deleteRepeat = function () {
            $.publish('formplayer.' + constants.DELETE_REPEAT, self);
            $.publish('formplayer.dirty');
        };

        self.hasAnyNestedQuestions = function () {
            return _.any(self.children(), function (d) {
                if (d.type() === constants.QUESTION_TYPE || d.type() === constants.REPEAT_TYPE || d.type() === constants.GROUPED_QUESTION_TILE_ROW_TYPE) {
                    return true;
                } else if (d.type() === constants.GROUP_TYPE) {
                    return d.hasAnyNestedQuestions();
                }
            });
        };

        self.isVisibleGroup = function () {
            const hasChildren = self.children().length !== 0;
            const hasLabel = !!ko.utils.unwrapObservable(self.caption_markdown) || !!self.caption();
            return hasChildren && hasLabel;
        };
    }
    Group.prototype = Object.create(Container.prototype);
    Group.prototype.constructor = Container;

    /**
     * Represents a repeat group. A repeat only has Group objects as children. Each child Group contains GroupedQuestionTileRow
     * objects which contains the child questions to be rendered
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
     */
    function Repeat(json, parent) {
        var self = this;
        self.parent = parent;

        Container.call(self, json);

        self.rel_ix = ko.observable(relativeIndex(self.ix()));
        if (_.has(json, 'domain_meta') && _.has(json, 'style')) {
            self.domain_meta = parseMeta(json.datatype, json.style);
        }
        self.templateType = 'repeat';
        self.ixInfo = function (o) {
            var fullIx = getIx(o);
            return o.rel_ix + (o.isRepetition ? '(' + o.uuid + ')' : '') + (o.rel_ix !== fullIx ? ' :: ' + fullIx : '');
        };

        self.newRepeat = function () {
            $.publish('formplayer.' + constants.NEW_REPEAT, self);
            $.publish('formplayer.dirty');
            $('.add').trigger('blur');
        };

        self.getTranslation = function (translationKey, defaultTranslation) {
            // Find the root level element which contains the translations.
            var curParent = getParentForm(self);
            var translations = curParent.translations;

            if (translations) {
                var addNewRepeatTranslation = ko.toJS(translations[translationKey]);
                if (addNewRepeatTranslation) {
                    return addNewRepeatTranslation;
                }
            }
            return defaultTranslation;
        };
    }
    Repeat.prototype = Object.create(Container.prototype);
    Repeat.prototype.constructor = Container;

    /**
     * Represents a group of questions. Questions are grouped such that all questions are
     * contained in the same row.
     * @param {Object} json - The JSON returned from touchforms to represent a Form
     * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
     */
    function GroupedQuestionTileRow(json, parent) {
        var self = this;
        self.parent = parent;
        Container.call(self, json);

        self.required = ko.observable(0);
        self.childrenRequired = ko.computed(function () {
            return _.find(self.children(), function (child) {
                return child.required();
            });
        });
    }
    GroupedQuestionTileRow.prototype = Object.create(Container.prototype);
    GroupedQuestionTileRow.prototype.constructor = Container;

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
        self.setWidths();
        // If the question has ever been answered, set this to true.
        self.hasAnswered = false;

        // if media question has been processed in FP successfully set to true
        self.formplayerProcessed = false;

        // pendingAnswer is a copy of an answer being submitted, so that we know not to reconcile a new answer
        // until the question has received a response from the server.
        self.pendingAnswer = ko.observable(constants.NO_PENDING_ANSWER);
        self.pendingAnswer.subscribe(function () { self.hasAnswered = true; });
        self.dirty = ko.computed(function () {
            return self.pendingAnswer() !== constants.NO_PENDING_ANSWER;
        });
        self.clean = ko.computed(function () {
            return !self.dirty() && !self.error() && !self.serverError() && self.hasAnswered;
        });
        self.hasError = ko.computed(function () {
            return (self.error() || self.serverError()) && !self.dirty();
        });

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

        self.is_select = (self.datatype() === 'select' || self.datatype() === 'multiselect');
        self.isLabel = self.datatype() === 'info';
        self.entry = entries.getEntry(self);
        self.entryTemplate = function () {
            return self.entry.templateType + '-entry-ko-template';
        };
        self.afterRender = function () { self.entry.afterRender(); };

        self.ixInfo = function (o) {
            var fullIx = getIx(o);
            return o.rel_ix + (o.isRepetition ? '(' + o.uuid + ')' : '') + (o.rel_ix !== fullIx ? ' :: ' + fullIx : '');
        };

        self.triggerAnswer = function () {
            self.pendingAnswer(_.clone(self.answer()));
            publishAnswerEvent();
        };
        var publishAnswerEvent = _.throttle(function () {
            $.publish('formplayer.dirty');
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
            var el = $("[for='" + self.entry.entryId + "']");
            $('html, body').animate({
                scrollTop: $(el).offset().top - 60,
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
                    return options.data ? markdown.render(DOMPurify.sanitize(options.data)) : null;
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
        var styleStr = (self.style) ? ko.utils.unwrapObservable(self.style.raw) : null;
        return getMatchingStyles(pattern, styleStr);
    };

    /**
     * Returns a boolean of whether the styles contain a pattern.
     * @param {Object} pattern - the regex or string used to find matching styles.
     */
    Question.prototype.stylesContains = function (pattern) {
        return this.stylesContaining(pattern).length > 0;
    };

    Question.prototype.setWidths = function () {
        const columnWidth = Question.calculateColumnWidthForPerRowStyle(this.style);

        if (columnWidth === constants.GRID_COLUMNS) {
            this.controlWidth = constants.CONTROL_WIDTH;
            this.labelWidth = constants.LABEL_WIDTH;
            this.questionTileWidth = constants.FULL_WIDTH;
        } else {
            this.controlWidth = constants.FULL_WIDTH;
            this.labelWidth = constants.FULL_WIDTH;
            this.questionTileWidth = `col-sm-${columnWidth}`;
        }
    };

    /**
     * Matches "<n>-per-row" style attributes. If a match if found, it calculates the column width
     * based on Bootstrap's 12 column grid system and returns the column width.
     * @param {Object} style - the appearance attributes
     */
    Question.calculateColumnWidthForPerRowStyle = function (style) {
        const styleStr = (style) ? ko.utils.unwrapObservable(style.raw) : null;
        const perRowPattern = new RegExp(`\\d+${constants.PER_ROW}(\\s|$)`);
        const matchingPerRowStyles = getMatchingStyles(perRowPattern, styleStr);
        const perRowStyle = matchingPerRowStyles.length === 0 ? null : matchingPerRowStyles[0];
        const itemsPerRow = perRowStyle !== null ? parseInt(perRowStyle.split("-")[0], 10) : null;

        return itemsPerRow !== null ? Math.round(constants.GRID_COLUMNS / itemsPerRow) : constants.GRID_COLUMNS;
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
    };
});
