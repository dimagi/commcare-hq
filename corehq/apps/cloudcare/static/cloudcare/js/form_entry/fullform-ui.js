/* globals CodeMirror */
var Formplayer = {
    Utils: {},
    Const: {},
    ViewModels: {},
    Errors: {}
};
var markdowner = window.markdownit();


//if index is part of a repeat, return only the part beyond the deepest repeat
function relativeIndex(ix) {
    var steps = ix.split(',');
    var deepest_repeat = -1,
        i;
    for (i = steps.length - 2; i >= 0; i--) {
        if (steps[i].indexOf(':') != -1) {
            deepest_repeat = i;
            break;
        }
    }
    if (deepest_repeat == -1) {
        return ix;
    } else {
        var rel_ix = '-';
        for (i = deepest_repeat + 1; i < steps.length; i++) {
            rel_ix += steps[i] + (i < steps.length - 1 ? ',' : '');
        }
        return rel_ix;
    }
}

function getIx(o) {
    var ix = o.rel_ix();
    while (ix[0] == '-') {
        o = o.parent;
        if (!o || ko.utils.unwrapObservable(o.rel_ix) === undefined) {
            break;
        }
        if (o.rel_ix().split(',').slice(-1)[0].indexOf(':') != -1) {
            ix = o.rel_ix() + ',' + ix.substring(1);
        }
    }
    return ix;
}

function getForIx(o, ix) {
    if (ko.utils.unwrapObservable(o.type) === 'question') {
        return (getIx(o) == ix ? o : null);
    } else {
        for (var i = 0; i < o.children().length; i++) {
            var result = getForIx(o.children()[i], ix);
            if (result) {
                return result;
            }
        }
    }
}

function ixInfo(o) {
    var full_ix = getIx(o);
    return o.rel_ix + (o.isRepetition ? '(' + o.uuid + ')' : '') + (o.rel_ix != full_ix ? ' :: ' + full_ix : '');
}

function parse_meta(type, style) {
    var meta = {};

    if (type == "date") {
        meta.mindiff = style.before !== null ? +style.before : null;
        meta.maxdiff = style.after !== null ? +style.after : null;
    } else if (type == "int" || type == "float") {
        meta.unit = style.unit;
    } else if (type == 'str') {
        meta.autocomplete = (style.mode == 'autocomplete');
        meta.autocomplete_key = style["autocomplete-key"];
        meta.mask = style.mask;
        meta.prefix = style.prefix;
        meta.longtext = (style.raw == 'full');
    } else if (type == "multiselect") {
        if (style["as-select1"]) {
            meta.as_single = [];
            var vs = style["as-select1"].split(',');
            for (var i = 0; i < vs.length; i++) {
                var k = +vs[i];
                if (k != 0) {
                    meta.as_single.push(k);
                }
            }
        }
    }

    if (type == "select" || type == "multiselect") {
        meta.appearance = style.raw;
    }

    return meta;
}

/**
 * Base abstract prototype for Repeat, Group and Form. Adds methods to
 * objects that contain a children array for rendering nested questions.
 * @param {Object} json - The JSON returned from touchforms to represent the container
 */
function Container(json) {
    var self = this;
    self.fromJS(json);

    /**
     * Used in KO template to determine what template to use for a child
     * @param {Object} child - The child object to be rendered, either Group, Repeat, or Question
     */
    self.childTemplate = function(child) {
        return ko.utils.unwrapObservable(child.type) + '-fullform-ko-template';
    };
}

/**
 * Reconciles the JSON representation of a Container (Group, Repeat, Form) and renders it into
 * a knockout representation.
 * @param {Object} json - The JSON returned from touchforms to represent a Container
 */
Container.prototype.fromJS = function(json) {
    var self = this;
    var mapping = {
        caption: {
            update: function(options) {
                return options.data ? DOMPurify.sanitize(options.data.replace(/\n/g, '<br/>')) : null;
            }
        },
        caption_markdown: {
            update: function(options) {
                return options.data ? markdowner.render(options.data) : null;
            }
        },
        children: {
            create: function(options) {
                if (options.data.type === Formplayer.Const.QUESTION_TYPE) {
                    return new Question(options.data, self);
                } else if (options.data.type === Formplayer.Const.GROUP_TYPE) {
                    return new Group(options.data, self);
                } else if (options.data.type === Formplayer.Const.REPEAT_TYPE) {
                    return new Repeat(options.data, self);
                } else {
                    console.error('Could not find question type of ' + options.data.type);
                }
            },
            update: function(options) {
                if (options.target.pendingAnswer &&
                        options.target.pendingAnswer() !== Formplayer.Const.NO_PENDING_ANSWER) {
                    // There is a request in progress
                    if (Formplayer.Utils.answersEqual(options.data.answer, options.target.pendingAnswer())) {
                        // We can now mark it as not dirty
                        options.data.answer = _.clone(options.target.pendingAnswer());
                        options.target.pendingAnswer(Formplayer.Const.NO_PENDING_ANSWER);
                    } else {
                        // still dirty, keep answer the same as the pending one
                        options.data.answer = _.clone(options.target.pendingAnswer());
                    }
                }

                // Do not update the answer if there is a server error on that question
                if (ko.utils.unwrapObservable(options.target.serverError)) {
                    options.data.answer = _.clone(options.target.answer());
                }
                return options.target;
            },
            key: function(data) {
                return ko.utils.unwrapObservable(data.uuid) || ko.utils.unwrapObservable(data.ix);
            }
        }
    }
    ko.mapping.fromJS(json, mapping, self);
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
    self.submitText = ko.observable('Submit');

    self.currentIndex = ko.observable("0");
    self.atLastIndex = ko.observable(false);

    var _updateIndexCallback = function (ix, isAtLastIndex) {
        self.currentIndex(ix.toString());
        self.atLastIndex(isAtLastIndex);
    };

    self.showInFormNavigation = ko.observable(
        self.displayOptions.oneQuestionPerScreen !== undefined
        && self.displayOptions.oneQuestionPerScreen() === true
    );

    self.isCurrentRequiredSatisfied = ko.computed(function () {
        if (!self.showInFormNavigation()) return true;

        return _.every(self.children(), function (q) {
            return (q.answer() === Formplayer.Const.NO_ANSWER && !q.required())
                || q.answer() !== null;
        });
    });

    self.enableNextButton = ko.computed(function () {
        if (!self.showInFormNavigation()) return false;

        var allValidAndNotPending = _.every(self.children(), function (q) {
            return q.isValid() && !q.pendingAnswer();
        });
        return allValidAndNotPending
            && self.showInFormNavigation()
            && self.isCurrentRequiredSatisfied()
            && !self.atLastIndex();
    });

    self.enablePreviousButton = ko.computed(function () {
        if (!self.showInFormNavigation()) return false;
        return self.currentIndex() !== "0" && self.currentIndex() !== "-1";
    });

    self.showSubmitButton = ko.computed(function () {
        return !self.showInFormNavigation();
    });

    self.submitForm = function(form) {
        $.publish('formplayer.' + Formplayer.Const.SUBMIT, self);
    };

    self.nextQuestion = function () {
        $.publish('formplayer.' + Formplayer.Const.NEXT_QUESTION, {
            callback: _updateIndexCallback,
            title: self.title(),
        });
    };

    self.prevQuestion = function () {
        $.publish('formplayer.' + Formplayer.Const.PREV_QUESTION, {
            callback: _updateIndexCallback,
            title: self.title(),
        });
    };

    $.unsubscribe('session');
    $.subscribe('session.reconcile', function(e, response, element) {
        // TODO where does response status parsing belong?
        if (response.status === 'validation-error') {
            if (response.type === 'required') {
                element.serverError('An answer is required');
            } else if (response.type === 'constraint') {
                element.serverError(response.reason || 'This answer is outside the allowed range.');
            }
            element.pendingAnswer(Formplayer.Const.NO_PENDING_ANSWER);
        } else {
            response.children = response.tree;
            delete response.tree;
            if (element.serverError) { element.serverError(null); }
            self.fromJS(response);
        }
    });

    $.subscribe('session.block', function(e, block) {
        $('#webforms input, #webforms textarea').prop('disabled', !!block);
    });

    self.submitting = function() {
        self.submitText('Submitting...');
    };
}
Form.prototype = Object.create(Container.prototype);
Form.prototype.constructor = Container;

/**
 * Represents a group of questions.
 * @param {Object} json - The JSON returned from touchforms to represent a Form
 * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
 */
function Group(json, parent) {
    var self = this;
    Container.call(self, json);

    self.parent = parent;
    self.rel_ix = ko.observable(relativeIndex(self.ix()));
    self.isRepetition = parent instanceof Repeat;
    if (json.hasOwnProperty('domain_meta') && json.hasOwnProperty('style')) {
        self.domain_meta = parse_meta(json.datatype, val);
    }

    if (self.isRepetition) {
        // If the group is part of a repetition the index can change if the user adds or deletes
        // repeat groups.
        self.ix.subscribe(function(newValue) {
            self.rel_ix(relativeIndex(self.ix()));
        });
    }

    self.deleteRepeat = function() {
        $.publish('formplayer.' + Formplayer.Const.DELETE_REPEAT, self);
        $.publish('formplayer.dirty');
    };

}
Group.prototype = Object.create(Container.prototype);
Group.prototype.constructor = Container;

/**
 * Represents a repeat group. A repeat only has Group objects as children. Each child Group contains the
 * child questions to be rendered
 * @param {Object} json - The JSON returned from touchforms to represent a Form
 * @param {Object} parent - The object's parent. Either a Form, Group, or Repeat.
 */
function Repeat(json, parent) {
    var self = this;
    Container.call(self, json);

    self.parent = parent;
    self.rel_ix = ko.observable(relativeIndex(self.ix()));
    if (json.hasOwnProperty('domain_meta') && json.hasOwnProperty('style')) {
        self.domain_meta = parse_meta(json.datatype, val);
    }
    self.templateType = 'repeat';

    self.newRepeat = function() {
        $.publish('formplayer.' + Formplayer.Const.NEW_REPEAT, self);
        $.publish('formplayer.dirty');
    };

}
Repeat.prototype = Object.create(Container.prototype);
Repeat.prototype.constructor = Container;

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
    self.error = ko.observable(null);
    self.serverError = ko.observable(null);
    self.rel_ix = ko.observable(relativeIndex(self.ix()));
    if (json.hasOwnProperty('domain_meta') && json.hasOwnProperty('style')) {
        self.domain_meta = parse_meta(json.datatype, val);
    }
    self.throttle = 200;

    // If the question has ever been answered, set this to true.
    self.hasAnswered = false;

    // pendingAnswer is a copy of an answer being submitted, so that we know not to reconcile a new answer
    // until the question has received a response from the server.
    self.pendingAnswer = ko.observable(Formplayer.Const.NO_PENDING_ANSWER);
    self.pendingAnswer.subscribe(function() { self.hasAnswered = true });
    self.dirty = ko.computed(function() {
        return self.pendingAnswer() !== Formplayer.Const.NO_PENDING_ANSWER;
    });
    self.clean = ko.computed(function() {
        return !self.dirty() && !self.error() && !self.serverError() && self.hasAnswered;
    });
    self.hasError = ko.computed(function() {
        return (self.error() || self.serverError()) && !self.dirty();
    });

    self.isValid = function() {
        return self.error() === null && self.serverError() === null;
    };

    self.is_select = (self.datatype() === 'select' || self.datatype() === 'multiselect');
    self.entry = getEntry(self);
    self.entryTemplate = function() {
        return self.entry.templateType + '-entry-ko-template';
    };
    self.afterRender = function() { self.entry.afterRender(); };

    self.onchange = _.throttle(function() {
        $.publish('formplayer.dirty');
        self.pendingAnswer(_.clone(self.answer()));
        $.publish('formplayer.' + Formplayer.Const.ANSWER, self);
    }, self.throttle);

    self.mediaSrc = function(resourceType) {
        if (!resourceType || !_.isFunction(Formplayer.resourceMap)) { return ''; }
        return Formplayer.resourceMap(resourceType);
    }
}

/**
 * Reconciles the JSON representation of a Question and renders it into
 * a knockout representation.
 * @param {Object} json - The JSON returned from touchforms to represent a Question
 */
Question.prototype.fromJS = function(json) {
    var self = this;
    var mapping = {
        caption: {
            update: function(options) {
                return options.data ? DOMPurify.sanitize(options.data.replace(/\n/g, '<br/>')) : null;
            }
        },
        caption_markdown: {
            update: function(options) {
                return options.data ? markdowner.render(options.data) : null;
            }
        },
    };

    ko.mapping.fromJS(json, mapping, self);
}


Formplayer.ViewModels.CloudCareDebugger = function() {
    var self = this;

    self.evalXPath = new Formplayer.ViewModels.EvaluateXPath();
    self.isMinimized = ko.observable(true);
    self.instanceXml = ko.observable('');
    self.formattedQuestionsHtml = ko.observable('');
    self.toggleState = function() {
        self.isMinimized(!self.isMinimized());
        // Wait to set the content heigh until after the CSS animation has completed.
        // In order to support multiple heights, we set the height with javascript since
        // a div inside a fixed position element cannot scroll unless a height is explicitly set.
        setTimeout(self.setContentHeight, 1001);
    };

    $.unsubscribe('debugger.update');
    $.subscribe('debugger.update', function(e) {
        $.publish('formplayer.' + Formplayer.Const.FORMATTED_QUESTIONS, function(resp) {
            self.formattedQuestionsHtml(resp.formattedQuestions);
            self.instanceXml(resp.instanceXml);
            self.evalXPath.autocomplete(resp.questionList);
            self.evalXPath.recentXPathQueries(resp.recentXPathQueries || []);
        });
    });

    self.setContentHeight = function() {
        var contentHeight;
        if (self.isMinimized()) {
            $('.debugger-content').outerHeight(0);
        } else {
            contentHeight = ($('.debugger').outerHeight() -
                $('.debugger-tab-title').outerHeight() -
                $('.debugger-navbar').outerHeight());
            $('.debugger-content').outerHeight(contentHeight);
        }
    };

    self.instanceXml.subscribe(function(newXml) {
        var $instanceTab = $('#debugger-xml-instance-tab'),
            codeMirror;

        codeMirror = CodeMirror(function(el) {
            $('#xml-viewer-pretty').html(el);
        }, {
            value: newXml,
            mode: 'xml',
            viewportMargin: Infinity,
            readOnly: true,
            lineNumbers: true,
        });
        $instanceTab.off();
        $instanceTab.on('shown.bs.tab', function() {
            codeMirror.refresh();
        });
    });

    // Called afterRender, ensures that the debugger takes the whole screen
    self.adjustWidth = function() {
        var $debug = $('#instance-xml-home'),
            $body = $('body');

        $debug.width($body.width() - $debug.offset().left);
    };
};

Formplayer.ViewModels.EvaluateXPath = function() {
    var self = this;
    self.xpath = ko.observable('');
    self.selectedXPath = ko.observable('');
    self.recentXPathQueries = ko.observableArray();
    self.$xpath = null;
    self.result = ko.observable('');
    self.success = ko.observable(true);
    self.onSubmitXPath = function() {
        self.evaluate(self.xpath());
    };
    self.onClickSelectedXPath = function() {
        if (self.selectedXPath()) {
            self.evaluate(self.selectedXPath());
        }
    };
    self.onClickSavedQuery = function(query) {
        self.xpath(query.xpath);
    };
    self.evaluate = function(xpath) {
        var callback = function(result, status) {
            self.result(result);
            self.success(status === "accepted");
        };
        $.publish('formplayer.' + Formplayer.Const.EVALUATE_XPATH, [xpath, callback]);
    };

    self.isSuccess = function(query) {
        return query.status === 'accepted';
    };

    self.onMouseUp = function() {
        var text = window.getSelection().toString();
        self.selectedXPath(text);
    };

    self.matcher = function(flag, subtext) {
        var match, regexp;
        // Match text that starts with the flag and then looks like a path.
        regexp = new RegExp('([\\s\(]+|^)' + RegExp.escape(flag) + '([\\w/-]*)$', 'gi');
        match = regexp.exec(subtext);
        return match ? match[2] : null;
    };

    /**
     * Set autocomplete for xpath input.
     *
     * @param {Array} autocompleteData - List of questions to be autocompleted for the xpath input
     */
    self.autocomplete = function(autocompleteData) {
        self.$xpath = $('#xpath');
        self.$xpath.atwho('destroy');
        self.$xpath.atwho('setIframe', window.frameElement, true);
        self.$xpath.atwho({
            at: '',
            data: autocompleteData,
            searchKey: 'value',
            maxLen: Infinity,
            displayTpl: function(d) {
                var icon = Formplayer.Utils.getIconFromType(d.type);
                return '<li><i class="' + icon + '"></i> ${value}</li>';
            },
            insertTpl: '${value}',
            callbacks: {
                matcher: self.matcher,
            },
        });
    };
};

/**
 * Used to compare if questions are equal to each other by looking at their index
 * @param {Object} e - Either the javascript object Question, Group, Repeat or the JSON representation
 */
var cmpkey = function(e) {
    var ix = ko.utils.unwrapObservable(e.ix);
    if (e.uuid) {
        return 'uuid-' + ko.utils.unwrapObservable(e.uuid);
    } else {
        return 'ix-' + (ix ? ix : getIx(e));
    }
}

/**
 * Given an element Question, Group, or Repeat, this will determine the index of the element in the set of
 * elements passed in. Returns -1 if not found
 * @param {Object} e - Either the javascript object Question, Group, Repeat or the JSON representation
 * @param {Object} set - The set of objects, either Question, Group, or Repeat to search in
 */
var ixElementSet = function(e, set) {
    return $.map(set, function(val) {
        return cmpkey(val);
    }).indexOf(cmpkey(e));
}

/**
 * Given an element Question, Group, or Repeat, this will return the element in the set of
 * elements passed in. Returns null if not found
 * @param {Object} e - Either the javascript object Question, Group, Repeat or the JSON representation
 * @param {Object} set - The set of objects, either Question, Group, or Repeat to search in
 */
var inElementSet = function(e, set) {
    var ix = ixElementSet(e, set);
    return (ix !== -1 ? set[ix] : null);
}


function scroll_pin(pin_threshold, $container, $elem) {
    return function() {
        var base_offset = $container.offset().top;
        var scroll_pos = $(window).scrollTop();
        var elem_pos = base_offset - scroll_pos;
        var pinned = (elem_pos < pin_threshold);

        $elem.css('top', pinned ? pin_threshold + 'px' : base_offset);
    };
}

function set_pin(pin_threshold, $container, $elem) {
    var pinfunc = scroll_pin(pin_threshold, $container, $elem);
    $(window).scroll(pinfunc);
    pinfunc();
}


Formplayer.Const = {
    GROUP_TYPE: 'sub-group',
    REPEAT_TYPE: 'repeat-juncture',
    QUESTION_TYPE: 'question',

    // Entry types
    STRING: 'str',
    INT: 'int',
    LONG_INT: 'longint',
    FLOAT: 'float',
    SELECT: 'select',
    MULTI_SELECT: 'multiselect',
    DATE: 'date',
    TIME: 'time',
    DATETIME: 'datetime',
    GEO: 'geo',
    INFO: 'info',

    // Note it's important to differentiate these two
    NO_PENDING_ANSWER: undefined,
    NO_ANSWER: null,

    // UI Config
    LABEL_WIDTH: 'col-sm-4',
    LABEL_OFFSET: 'col-sm-offset-4',
    CONTROL_WIDTH: 'col-sm-8',

    // XForm Navigation
    QUESTIONS_FOR_INDEX: 'questions_for_index',
    NEXT_QUESTION: 'next_index',
    PREV_QUESTION: 'prev_index',

    // XForm Actions
    NEW_FORM: 'new-form',
    ANSWER: 'answer',
    CURRENT: 'current',
    EVALUATE_XPATH: 'evaluate-xpath',
    NEW_REPEAT: 'new-repeat',
    DELETE_REPEAT: 'delete-repeat',
    SET_LANG: 'set-lang',
    SUBMIT: 'submit-all',
    FORMATTED_QUESTIONS: 'formatted_questions',

    // Control values. See commcare/javarosa/src/main/java/org/javarosa/core/model/Constants.java
    CONTROL_UNTYPED: -1,
    CONTROL_INPUT: 1,
    CONTROL_SELECT_ONE: 2,
    CONTROL_SELECT_MULTI: 3,
    CONTROL_TEXTAREA: 4,
    CONTROL_SECRET: 5,
    CONTROL_RANGE: 6,
    CONTROL_UPLOAD: 7,
    CONTROL_SUBMIT: 8,
    CONTROL_TRIGGER: 9,
    CONTROL_IMAGE_CHOOSE: 10,
    CONTROL_LABEL: 11,
    CONTROL_AUDIO_CAPTURE: 12,
    CONTROL_VIDEO_CAPTURE: 13,

    //knockout timeouts
    KO_ENTRY_TIMEOUT: 500,

};

Formplayer.Errors = {
    GENERIC_ERROR: "Something unexpected went wrong on that request. " +
        "If you have problems filling in the rest of your form please submit an issue. " +
        "Technical Details: ",
    TIMEOUT_ERROR: "CommCareHQ has detected a possible network connectivity problem. " +
        "Please make sure you are connected to the " +
        "Internet in order to submit your form."
};

Formplayer.Utils.touchformsError = function(message) {
    return Formplayer.Errors.GENERIC_ERROR + message;
};

/**
 * Compares the equality of two answer sets.
 * @param {(string|string[])} answer1 - A string of answers or a single answer
 * @param {(string|string[])} answer2 - A string of answers or a single answer
 */
Formplayer.Utils.answersEqual = function(answer1, answer2) {
    if (answer1 instanceof Array && answer2 instanceof Array) {
        return _.isEqual(answer1, answer2);
    } else if (answer1 === answer2) {
        return true;
    }
    return false;
};

/**
 * Initializes a new form to be used by the formplayer.
 * @param {Object} formJSON - The json representation of the form
 * @param {Object} resourceMap - Function for resolving multimedia paths
 * @param {Object} $div - The jquery element that the form will be rendered in.
 */
Formplayer.Utils.initialRender = function(formJSON, resourceMap, $div) {
    var form = new Form(formJSON),
        $debug = $('#cloudcare-debugger'),
        cloudCareDebugger;
    Formplayer.resourceMap = resourceMap;
    ko.cleanNode($div[0]);
    $div.koApplyBindings(form);

    if ($debug.length) {
        cloudCareDebugger = new Formplayer.ViewModels.CloudCareDebugger();
        ko.cleanNode($debug[0]);
        $debug.koApplyBindings(cloudCareDebugger);
    }

    return form;
};

Formplayer.Utils.getIconFromType = function(type) {
    var icon = '';
    switch (type) {
    case 'Trigger':
        icon = 'fcc fcc-fd-variable';
        break;
    case 'Text':
        icon = 'fcc fcc-fd-text';
        break;
    case 'PhoneNumber':
        icon = 'fa fa-signal';
        break;
    case 'Secret':
        icon = 'fa fa-key';
        break;
    case 'Integer':
        icon = 'fcc fcc-fd-numeric';
        break;
    case 'Audio':
        icon = 'fcc fcc-fd-audio-capture';
        break;
    case 'Image':
        icon = 'fa fa-camera';
        break;
    case 'Video':
        icon = 'fa fa-video-camera';
        break;
    case 'Signature':
        icon = 'fcc fcc-fd-signature';
        break;
    case 'Geopoint':
        icon = 'fa fa-map-marker';
        break;
    case 'Barcode Scan':
        icon = 'fa fa-barcode';
        break;
    case 'Date':
        icon = 'fa fa-calendar';
        break;
    case 'Date and Time':
        icon = 'fcc fcc-fd-datetime';
        break;
    case 'Time':
        icon = 'fcc fcc-fa-clock-o';
        break;
    case 'Select':
        icon = 'fcc fcc-fd-single-select';
        break;
    case 'Double':
        icon = 'fcc fcc-fd-decimal';
        break;
    case 'Label':
        icon = 'fa fa-tag';
        break;
    case 'MSelect':
        icon = 'fcc fcc-fd-multi-select';
        break;
    case 'Multiple Choice':
        icon = 'fcc fcc-fd-single-select';
        break;
    case 'Group':
        icon = 'fa fa-folder-open';
        break;
    case 'Question List':
        icon = 'fa fa-reorder';
        break;
    case 'Repeat Group':
        icon = 'fa fa-retweet';
        break;
    case 'Function':
        icon = 'fa fa-calculator';
        break;
    }
    return icon;
};

RegExp.escape= function(s) {
    return s.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
};
