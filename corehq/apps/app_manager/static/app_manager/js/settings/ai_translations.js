/**
 * "Translate with AI" panel on the app Languages page: one row per
 * language, showing the live status of a run, then the summary of a
 * finished run (kept for a day), then the last run that saved anything.
 */
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";

const POLL_INTERVAL = 3000;
const MAX_POLL_INTERVAL = 60000;
// failed labels shown for each reason until "Show all"
const FAILED_LABELS_SHOWN = 10;
// the states of AITranslationStatus; the active ones come from the page
const STATE = Object.freeze({
    QUEUED: "queued",
    TRANSLATING: "translating",
    APPLYING: "applying",
    DONE: "done",
    ERROR: "error",
});
// so a status isn't told apart by colour alone
const BADGE_ICONS = Object.freeze({
    "text-bg-secondary": "fa-minus",
    "text-bg-info": "fa-spinner fa-spin",
    "text-bg-success": "fa-check",
    "text-bg-warning": "fa-triangle-exclamation",
    "text-bg-danger": "fa-xmark",
});

var panelModel = function (options) {
    var self = {};
    var timer = null;
    var requestInFlight = false;
    var failedPolls = 0;
    // a poll sent before a run was started may predate it; its response is dropped
    var runsStarted = 0;

    self.canEdit = options.canEdit;
    self.activeStates = options.activeStates;
    self.limitReached = options.limitReached;
    self.languagesChanged = ko.observable(false);
    self.languages = options.languages.map(function (language) {
        return languageModel(language, self);
    });

    self.pollSoon = function (delay) {
        clearTimeout(timer);
        timer = setTimeout(pollStatus, delay);
    };

    self.runStarted = function () {
        runsStarted++;
        self.pollSoon(POLL_INTERVAL);
    };

    function pollStatus() {
        // the status URL needs edit permission
        if (!self.canEdit || document.hidden || requestInFlight) {
            return;
        }
        requestInFlight = true;
        var runsStartedWhenSent = runsStarted;
        $.get(initialPageData.reverse("ai_translation_status"))
            .done(function (statuses) {
                failedPolls = 0;
                if (runsStartedWhenSent === runsStarted) {
                    self.languages.forEach(function (language) {
                        if (language.code in statuses) {
                            language.status(statuses[language.code]);
                        }
                    });
                }
                if (self.languages.some(function (language) { return language.isActive(); })) {
                    self.pollSoon(POLL_INTERVAL);
                }
            })
            .fail(function (xhr) {
                if (xhr.status === 403 || xhr.status === 404) {
                    return;
                }
                failedPolls++;
                self.pollSoon(Math.min(POLL_INTERVAL * Math.pow(2, failedPolls), MAX_POLL_INTERVAL));
            })
            .always(function () {
                requestInFlight = false;
            });
    }

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            self.pollSoon(0);
        }
    });

    // the language list saves without reloading the page
    $(document).ajaxSuccess(function (event, xhr, settings) {
        if (settings.url === initialPageData.reverse("edit_app_langs")) {
            self.languagesChanged(true);
        }
    });

    self.pollSoon(0);
    return self;
};

var languageModel = function (options, panel) {
    var self = {};
    self.code = options.code;
    // a code without a known name shows on its own
    self.label = options.name
        ? interpolate(gettext("%(name)s (%(code)s)"), {name: options.name, code: options.code}, true)
        : options.code;
    self.supported = options.supported;
    self.status = ko.observable({});
    // the last run that saved anything, including one finished on this page
    self.savedRun = ko.observable(options.last_run);
    self.starting = ko.observable(false);
    self.startError = ko.observable("");
    var failedLabelsRun;  // when the run the failed-label list is for finished

    self.status.subscribe(function (status) {
        if (status.state === STATE.DONE && status.translated) {
            self.savedRun(savedRunFromStatus(status, options.last_run));
        }
        // polls repeat a run's status; only another run's replaces the list
        if (status.finished_on !== failedLabelsRun) {
            failedLabelsRun = status.finished_on;
            self.failedLabels(null);
            self.failedLabelsExpired(false);
            self.failedLabelsError(false);
            self.showFailedLabels(false);
            self.showAllFailedLabels(false);
        }
    });

    // the labels the finished run couldn't translate, fetched when asked
    // for. A run that failed outright can have them too, e.g. when every
    // batch failed; queued and running statuses never have a count.
    self.failedLabelCount = ko.computed(function () {
        return self.status().failed_label_count || 0;
    });
    self.failedLabels = ko.observable(null);  // null until fetched
    self.failedLabelsExpired = ko.observable(false);
    self.failedLabelsError = ko.observable(false);
    self.loadingFailedLabels = ko.observable(false);
    self.showFailedLabels = ko.observable(false);
    self.showAllFailedLabels = ko.observable(false);
    // for the toggle's aria-controls
    self.failedLabelsId = "ai-translation-failed-labels-" + self.code;
    self.failedLabelGroups = ko.computed(function () {
        return groupByReason(self.failedLabels() || [], self.showAllFailedLabels());
    });
    self.failedLabelsLine = ko.computed(function () {
        return interpolate(ngettext(
            "%(count)s label couldn't be translated",
            "%(count)s labels couldn't be translated",
            self.failedLabelCount()), {count: _number(self.failedLabelCount())}, true);
    });
    // the saved list stops at a limit; the count is every label that failed
    self.failedLabelsCutLine = ko.computed(function () {
        var shown = (self.failedLabels() || []).length;
        if (!shown || shown >= self.failedLabelCount()) {
            return "";
        }
        return interpolate(gettext("Showing the first %(shown)s of %(count)s labels."), {
            shown: _number(shown),
            count: _number(self.failedLabelCount()),
        }, true);
    });
    self.anyFailedLabelsHidden = ko.computed(function () {
        return self.failedLabelGroups().some(function (group) { return group.hidden; });
    });

    self.toggleFailedLabels = function () {
        self.showFailedLabels(!self.showFailedLabels());
        if (self.showFailedLabels() && !self.failedLabels() && !self.loadingFailedLabels()) {
            fetchFailedLabels();
        }
    };

    self.showAllLabels = function () {
        self.showAllFailedLabels(true);
    };

    var fetchFailedLabels = function () {
        var run = failedLabelsRun;
        self.loadingFailedLabels(true);
        self.failedLabelsError(false);
        self.failedLabelsExpired(false);
        $.get(initialPageData.reverse("ai_translation_failed_labels"), {lang: self.code})
            .done(function (data) {
                // a newer run finished meanwhile; its list replaces this one
                if (run !== failedLabelsRun) {
                    return;
                }
                self.failedLabelsExpired(data.labels === null);
                self.failedLabels(data.labels || []);
            })
            .fail(function () {
                if (run !== failedLabelsRun) {
                    return;
                }
                self.failedLabelsError(true);
                self.showFailedLabels(false);
            })
            .always(function () {
                self.loadingFailedLabels(false);
                // the newer run's list was asked for while this one loaded
                if (run !== failedLabelsRun && self.showFailedLabels() && !self.failedLabels()) {
                    fetchFailedLabels();
                }
            });
    };

    self.isActive = ko.computed(function () {
        return panel.activeStates.includes(self.status().state);
    });
    self.display = ko.computed(function () {
        return statusDisplay(self.supported, self.status(), self.savedRun());
    });
    self.lastRun = ko.computed(function () {
        return lastRunDisplay(self.savedRun());
    });
    self.canStart = ko.computed(function () {
        return self.supported && !self.isActive() && !self.starting() && !panel.limitReached;
    });

    self.start = function () {
        self.starting(true);
        self.startError("");
        $.post(initialPageData.reverse("start_ai_translation"), {lang: self.code})
            .done(function () {
                self.status({state: STATE.QUEUED});
                panel.runStarted();
            })
            .fail(function (xhr) {
                if (xhr.status === 409) {
                    // already queued or running, e.g. from another tab
                    self.status({state: STATE.QUEUED});
                    panel.runStarted();
                    return;
                }
                var error = (xhr.responseJSON || {}).error;
                if (!error && xhr.status === 403) {
                    // e.g. the user's permissions changed since the page loaded
                    error = gettext("You need permission to edit this app to translate it.");
                }
                self.startError(error || gettext("The translation couldn't be started. Try again."));
            })
            .always(function () {
                self.starting(false);
            });
    };

    return self;
};

/**
 * A finished run that saved translations, in the shape of a page-load
 * ``last_run``. Its changes are only in a build if the build the page
 * loaded with is at least as new as the version the run saved.
 */
var savedRunFromStatus = function (status, pageLoadRun) {
    return {
        strings_attempted: status.total,
        strings_translated: status.translated,
        total_app_strings: status.total_app_strings,
        total_app_strings_ai_translated: status.total_app_strings_ai_translated,
        created_on: status.finished_on,
        in_version: pageLoadRun && pageLoadRun.in_version >= status.app_version
            ? pageLoadRun.in_version : null,
    };
};

/**
 * Failed labels grouped by why they failed, in the order each reason
 * first appears. Until ``showAll``, each group shows its first few.
 */
var groupByReason = function (labels, showAll) {
    var groups = [];
    var byReason = {};
    labels.forEach(function (label) {
        if (!(label.reason in byReason)) {
            byReason[label.reason] = {reason: label.reason, labels: []};
            groups.push(byReason[label.reason]);
        }
        byReason[label.reason].labels.push(label);
    });
    return groups.map(function (group) {
        var hidden = showAll ? 0 : Math.max(group.labels.length - FAILED_LABELS_SHOWN, 0);
        return {
            reason: group.reason,
            count: _number(group.labels.length),
            labels: showAll ? group.labels : group.labels.slice(0, FAILED_LABELS_SHOWN),
            hidden: hidden,
            hiddenLine: interpolate(gettext("and %(count)s more"), {count: _number(hidden)}, true),
        };
    });
};

/**
 * The status label and detail lines for one language.
 */
var statusDisplay = function (supported, status, lastRun) {
    var display = {
        label: "", labelClass: "text-bg-secondary", detail: "", progress: null, share: "", partial: false,
    };
    if (!supported) {
        display.label = gettext("Not yet supported");
        display.detail = gettext("Use the manual translation options below");
    } else if (status.state === STATE.QUEUED) {
        display.label = gettext("Starting…");
        display.labelClass = "text-bg-info";
        display.detail = gettext("Queued");
    } else if (status.state === STATE.TRANSLATING) {
        display.label = gettext("Translating…");
        display.labelClass = "text-bg-info";
        if (status.batches_total) {
            display.detail = interpolate(gettext("Batch %(batch)s of %(total)s"), {
                batch: Math.min(status.batches_done + 1, status.batches_total),
                total: status.batches_total,
            }, true);
            display.progress = Math.round(100 * status.batches_done / status.batches_total);
        }
    } else if (status.state === STATE.APPLYING) {
        display.label = gettext("Applying translations…");
        display.labelClass = "text-bg-info";
        display.detail = gettext("Saving to the app");
    } else if (status.state === STATE.DONE) {
        _finishedRunDisplay(display, status);
        display.share = _appShare(lastRun);
    } else if (status.state === STATE.ERROR) {
        display.label = gettext("Failed");
        display.labelClass = "text-bg-danger";
        display.detail = status.message;
    } else {
        _lastRunStatusDisplay(display, lastRun);
        display.share = _appShare(lastRun);
    }
    display.icon = BADGE_ICONS[display.labelClass];
    return display;
};

var _finishedRunDisplay = function (display, status) {
    if (!status.total) {
        display.label = gettext("Nothing to translate");
        display.labelClass = "text-bg-success";
        display.detail = gettext("Every label already has a translation.");
    } else if (status.translated === status.total) {
        display.label = gettext("AI translated");
        display.labelClass = "text-bg-success";
        display.detail = interpolate(ngettext(
            "%(count)s label translated in this run",
            "%(count)s labels translated in this run",
            status.translated), {count: _number(status.translated)}, true);
    } else {
        display.label = gettext("Finished with errors");
        display.labelClass = "text-bg-warning";
        display.partial = true;
        var parts = [interpolate(gettext("%(translated)s of %(total)s labels translated (%(percent)s%)"), {
            translated: _number(status.translated),
            total: _number(status.total),
            percent: _percent(status.translated, status.total),
        }, true)];
        // labels that were skipped or failed are listed under the status
        if (status.changed) {
            parts.push(interpolate(gettext("%(count)s changed during the run"), {count: _number(status.changed)}, true));
        }
        // how to translate the rest is in the template, under the status
        display.detail = parts.join(" · ");
    }
};

var _lastRunStatusDisplay = function (display, lastRun) {
    if (!lastRun) {
        display.label = gettext("No AI run yet");
        return;
    }
    if (lastRun.strings_translated === lastRun.strings_attempted) {
        display.label = gettext("AI translated");
        display.labelClass = "text-bg-success";
        display.detail = interpolate(ngettext(
            "%(count)s label translated in the last run",
            "%(count)s labels translated in the last run",
            lastRun.strings_translated), {count: _number(lastRun.strings_translated)}, true);
    } else {
        display.label = gettext("Partially translated");
        display.labelClass = "text-bg-warning";
        display.partial = true;
        display.detail = interpolate(gettext(
            "%(translated)s of %(attempted)s labels translated in the last run · " +
            "%(missed)s weren't translated"), {
            translated: _number(lastRun.strings_translated),
            attempted: _number(lastRun.strings_attempted),
            missed: _number(lastRun.strings_attempted - lastRun.strings_translated),
        }, true);
    }
};

/**
 * The "Last AI run" date and version line for one language.
 */
var lastRunDisplay = function (lastRun) {
    if (!lastRun) {
        return {date: "—", version: ""};
    }
    return {date: _formatDate(lastRun.created_on), version: _versionLine(lastRun.in_version)};
};

/**
 * How much of the whole app is AI translated as of a run, or an empty
 * string if unknown. Unlike a run's own counts, this doesn't depend on
 * which run happened last.
 */
var _appShare = function (run) {
    if (!run || !run.total_app_strings) {
        return "";
    }
    return interpolate(gettext("AI translated %(percent)s% of the Application (%(translated)s of %(total)s labels)"), {
        percent: _percent(run.total_app_strings_ai_translated, run.total_app_strings),
        translated: _number(run.total_app_strings_ai_translated),
        total: _number(run.total_app_strings),
    }, true);
};

var _versionLine = function (inVersion) {
    return inVersion
        ? interpolate(gettext("In version %(version)s"), {version: inVersion}, true)
        : gettext("Not in a version yet");
};

// 100% and 0% only when it's all or nothing: 1,359 of 1,360 is 99%, not 100%
var _percent = function (part, whole) {
    var percent = Math.round(100 * part / whole);
    if (part < whole) {
        percent = Math.min(percent, 99);
    }
    if (part > 0) {
        percent = Math.max(percent, 1);
    }
    return percent;
};

var _number = function (value) {
    return value.toLocaleString(document.documentElement.lang || undefined);
};

var _formatDate = function (isoDate) {
    return new Date(isoDate).toLocaleDateString(document.documentElement.lang || undefined,
        {year: "numeric", month: "short", day: "numeric"});
};

$(function () {
    var $panel = $("#ai-translations-panel");
    if ($panel.length) {
        $panel.koApplyBindings(panelModel({
            canEdit: initialPageData.get("ai_translation_can_edit"),
            languages: initialPageData.get("ai_translation_languages"),
            activeStates: initialPageData.get("ai_translation_active_states"),
            limitReached: initialPageData.get("ai_translation_limit_reached"),
        }));
    }
});
