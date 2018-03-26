/* globals JSON */
hqDefine('analytix/js/logging', [
    'underscore',
    'analytix/js/initial',
], function (
    _,
    initialAnalytics
) {
    'use strict';

    var _makeLevel = function (name, style) {
        return {
            name: name,
            style: style,
        };
    };

    var _LEVELS = {
        warning: _makeLevel('WARNING', 'color: #994f00;'),
        verbose: _makeLevel('VERBOSE', 'color: #685c53;'),
        debug: _makeLevel('DEBUG', 'color: #004ebc;'),
    };

    var _printPretty = function (msg) {
        var _title, _value, _group;
        if (_.isUndefined(msg.value)) {
            console.log("Message was undefined");  // eslint-disable-line no-console
        } else if (msg.value.isGroup) {
            _group = msg.value;
            _group.level = msg.level;
            _group.print();
        } else if (_.isArguments(msg.value)) {
            _title = "Arguments (" + msg.value.length + ")    " + _.map(Array.from(msg.value), JSON.stringify).join('    ');
            _value = Array.from(msg.value);
            _group = group(_title, message(_value, msg.level));
            _group.isCollapsed = true;
            _group.print();
        } else if (_.isArray(msg.value)) {
            _.each(msg.value, function (msg) {
                _printPretty(message(msg, msg.level));
            });
        } else if (_.isObject(msg.value) && _.has(msg.value, 0) && _.isElement(msg.value[0])) {
            // DOM element
            _title = "#" + msg.value.get(0).id + " ." + msg.value.get(0).className.split(' ').join('.');
            _value = msg.value.get(0).outerHTML;
            _group = group(_title, message(_value, msg.level));
            _group.isCollapsed = true;
            _group.print();
        } else if (!_.isString(msg.value) && !_.isUndefined(msg.value)) {
            _title = JSON.stringify(msg.value);
            _value = msg.value;
            _group = group(_title, message(_value, msg.level));
            _group.isCollapsed = true;
            _group.isRaw = true;
            _group.print();
        } else {
            msg.print();
        }
    };

    var _getStyle = function (level) {
        var levelOptions = _LEVELS[level];
        return (levelOptions) ? levelOptions.style : "";
    };

    var message = function (value, level) {
        var msg = {};
        msg.level = level;
        msg.value = value;
        msg.print = function () {
            console.log(msg.value);  // eslint-disable-line no-console
        };
        return msg;
    };

    /**
     * Used to format console log messages better by combining them into
     * groups so that it's easier to skim data vs info text on the console output
     * and improve readability.
     */
    var group = function (title, message) {
        var grp = {};
        grp.title = title;
        grp.level = message.level;
        grp.message = message;
        grp.isCollapsed = false;
        grp.isRaw = false;
        grp.isGroup = true;
        grp.print = function () {
            var _printGrp = (grp.isCollapsed) ? console.groupCollapsed : console.group;  // eslint-disable-line no-console
            _printGrp("%c%s", _getStyle(grp.level), grp.title);
            (grp.isRaw) ? grp.message.print() : _printPretty(grp.message);
            console.groupEnd();  // eslint-disable-line no-console
        };
        return grp;
    };

    var Log = function(level, logger) {
        var _log = {};
        _log.level = level.slug;
        _log.isVisible = level.isVisible;

        /**
         * Helper function for creating the logging prefix.
         * @returns {string}
         * @private
         */
        _log.getPrefix = function (messagePrefix) {
            var prefix = _.compact(_.flatten([level.prefix, logger.prefix, _log.category, messagePrefix]));
            return prefix.join(' | ') + '    ';
        };
        return {
            getPrint: function () {
                return function (messageValue, messagePrefix) {
                    if (_log.isVisible) {
                        group(_log.getPrefix(messagePrefix), message(messageValue, _log.level)).print();
                    }
                };
            },
            setCategory: function (category) {
                _log.category = category;
            },
        };
    };

    var levels = ['warning', 'debug', 'verbose'];
    var level = function (_levelSlug, _levelPrefix, _logger) {
        var globalLevel = initialAnalytics.getFn('global')('logLevel'),
            isVisible = levels.indexOf(_levelSlug) <= levels.indexOf(globalLevel),
            _levelData = {
                slug: _levelSlug,
                prefix: _levelPrefix,
                isVisible: isVisible,
            },
            level = {};
        level.addCategory = function (slug, category) {
            if (_.isUndefined(level[slug])) {
                var _log = Log(_levelData, _logger);
                _log.setCategory(category);
                level[slug] = _log.getPrint();
            }
        };
        level.addCategory('log');
        return level;
    };

    var logger = function (_prefix) {
        var logger = {};
        logger.prefix = _prefix;
        logger.createLevel = function (slug, name) {
            return level(slug, name, logger);
        };
        _.each(_LEVELS, function (options, key) {
            logger[key] = logger.createLevel(key, options.name);
        });
        logger.fmt = {};
        logger.fmt.groupMsg = function (title, msg) {
            return group(title, message(msg));
        };
        /**
         * Outputs a list of group messages that maps argument labels to their values.
         * @param {string[]} labels
         * @param {Arguments} args
         */
        logger.fmt.labelArgs = function (labels, args) {
            return _.compact(_.map(labels, function (label, ind) {
                if (args[ind]) {
                    return logger.fmt.groupMsg(label, args[ind]);
                }
            }));
        };
        return logger;
    };

    return {
        getLoggerForApi: function (apiName) {
            return logger(apiName);
        },
    };
});
