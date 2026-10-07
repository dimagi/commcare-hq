/**
 * "Translate with AI" panel on the app Languages page: one row per
 * language, showing the live status of a run, then the summary of a
 * finished run (kept for a day), then the last run that saved anything.
 */
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import google from "analytix/js/google";

const POLL_INTERVAL = 3000;
const MAX_POLL_INTERVAL = 60000;
const ACTIVE_STATES = ["queued", "translating", "applying"];

var panelModel = function (options) {
    var self = {};
    var timer = null;
    var requestInFlight = false;
    var failedPolls = 0;
    // a poll sent before a run was started may predate it; its response is dropped
    var runsStarted = 0;

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
        if (document.hidden || requestInFlight) {
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
    self.supported = options.supported;
    self.status = ko.observable({});
    self.starting = ko.observable(false);
    self.startError = ko.observable("");

    self.isActive = ko.computed(function () {
        return ACTIVE_STATES.includes(self.status().state);
    });
    self.display = ko.computed(function () {
        return statusDisplay(self.supported, self.status(), options.last_run);
    });
    self.lastRun = ko.computed(function () {
        return lastRunDisplay(self.status(), options.last_run);
    });
    self.canStart = ko.computed(function () {
        return self.supported && !self.isActive() && !self.starting() && !panel.limitReached;
    });

    // counts runs this page saw fail, not ones that had failed before it loaded
    var previousState;
    self.status.subscribe(function (status) {
        previousState = status.state;
    }, null, "beforeChange");
    self.status.subscribe(function (status) {
        if (status.state === "error" && ACTIVE_STATES.includes(previousState)) {
            google.track.event("AI App Translations", "Run failed", self.code);
        }
    });

    self.start = function () {
        google.track.event("AI App Translations", "AI Translate", self.code);
        self.starting(true);
        self.startError("");
        $.post(initialPageData.reverse("start_ai_translation"), {lang: self.code})
            .done(function () {
                self.status({state: "queued"});
                panel.runStarted();
            })
            .fail(function (xhr) {
                if (xhr.status === 409) {
                    // already queued or running, e.g. from another tab
                    self.status({state: "queued"});
                    panel.runStarted();
                    return;
                }
                self.startError((xhr.responseJSON || {}).error
                    || gettext("The translation couldn't be started. Try again."));
            })
            .always(function () {
                self.starting(false);
            });
    };

    return self;
};

/**
 * The status label and detail lines for one language.
 */
var statusDisplay = function (supported, status, lastRun) {
    var display = {
        label: "", labelClass: "text-bg-secondary", detail: "", warning: "", progress: null, share: null,
    };
    if (!supported) {
        display.label = gettext("Not yet supported");
        display.detail = gettext("Use the manual translation options below");
    } else if (status.state === "queued") {
        display.label = gettext("Starting…");
        display.labelClass = "text-bg-info";
        display.detail = gettext("Queued");
    } else if (status.state === "translating") {
        display.label = gettext("Translating…");
        display.labelClass = "text-bg-info";
        if (status.batches_total) {
            display.detail = interpolate(gettext("Batch %(batch)s of %(total)s"), {
                batch: Math.min(status.batches_done + 1, status.batches_total),
                total: status.batches_total,
            }, true);
            display.progress = Math.round(100 * status.batches_done / status.batches_total);
        }
    } else if (status.state === "applying") {
        display.label = gettext("Applying translations…");
        display.labelClass = "text-bg-info";
        display.detail = gettext("Saving to the app");
    } else if (status.state === "done") {
        _finishedRunDisplay(display, status);
        display.share = _appShare(status.total_app_strings ? status : lastRun);
    } else if (status.state === "error") {
        display.label = gettext("Failed");
        display.labelClass = "text-bg-danger";
        display.detail = status.message;
    } else {
        _lastRunStatusDisplay(display, lastRun);
        display.share = _appShare(lastRun);
    }
    return display;
};

var _finishedRunDisplay = function (display, status) {
    // a finished run's message is a warning, e.g. many strings skipped
    display.warning = status.message || "";
    if (!status.total) {
        display.label = gettext("Nothing to translate");
        display.labelClass = "text-bg-success";
        display.detail = gettext("Every string already has a translation.");
    } else if (status.translated === status.total) {
        display.label = gettext("AI translated");
        display.labelClass = "text-bg-success";
        display.detail = interpolate(ngettext(
            "%(count)s string translated in this run",
            "%(count)s strings translated in this run",
            status.translated), {count: _number(status.translated)}, true);
    } else {
        display.label = gettext("Finished with errors");
        display.labelClass = "text-bg-warning";
        var parts = [interpolate(gettext("%(translated)s of %(total)s strings translated (%(percent)s%)"), {
            translated: _number(status.translated),
            total: _number(status.total),
            percent: Math.round(100 * status.translated / status.total),
        }, true)];
        if (status.skipped) {
            parts.push(interpolate(gettext("%(count)s skipped"), {count: _number(status.skipped)}, true));
        }
        if (status.failed) {
            parts.push(interpolate(gettext("%(count)s failed"), {count: _number(status.failed)}, true));
        }
        if (status.changed) {
            parts.push(interpolate(gettext("%(count)s changed during the run"), {count: _number(status.changed)}, true));
        }
        display.detail = parts.join(" · ") + ". "
            + gettext("Run AI Translate again to retry the strings that weren't translated.");
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
            "%(count)s string translated in the last run",
            "%(count)s strings translated in the last run",
            lastRun.strings_translated), {count: _number(lastRun.strings_translated)}, true);
    } else {
        display.label = gettext("Partially translated");
        display.labelClass = "text-bg-warning";
        display.detail = interpolate(gettext(
            "%(translated)s of %(attempted)s strings translated in the last run · " +
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
var lastRunDisplay = function (status, lastRun) {
    if (status.state === "done" && status.translated) {
        var inVersion = lastRun && lastRun.in_version >= status.app_version ? lastRun.in_version : null;
        return {date: _formatDate(status.finished_on), version: _versionLine(inVersion)};
    }
    if (!lastRun) {
        return {date: "—", version: ""};
    }
    return {date: _formatDate(lastRun.created_on), version: _versionLine(lastRun.in_version)};
};

/**
 * How much of the whole app is AI translated as of a run, or null if
 * unknown. Unlike a run's own counts, this doesn't depend on which run
 * happened last.
 */
var _appShare = function (run) {
    if (!run || !run.total_app_strings) {
        return null;
    }
    var percent = Math.round(100 * run.total_app_strings_ai_translated / run.total_app_strings);
    return {
        percent: percent,
        text: interpolate(gettext("%(percent)s% of the app AI translated (%(translated)s of %(total)s strings)"), {
            percent: percent,
            translated: _number(run.total_app_strings_ai_translated),
            total: _number(run.total_app_strings),
        }, true),
    };
};

var _versionLine = function (inVersion) {
    return inVersion
        ? interpolate(gettext("In version %(version)s"), {version: inVersion}, true)
        : gettext("Not in a version yet");
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
            languages: initialPageData.get("ai_translation_languages"),
            limitReached: initialPageData.get("ai_translation_limit_reached"),
        }));
    }
});
