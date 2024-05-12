'use strict';
hqDefine('analytix/js/logging', [
    'underscore',
    'analytix/js/initial',
], function (
    _,
    initialAnalytics
) {

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

    var _printPretty = function (message) {
        var _title, _value, _group;
        if (_.isUndefined(message.value)) {
            console.log("Message was undefined");  // eslint-disable-line no-console
        } else if (message.value.isGroup) {
            _group = message.value;
            _group.level = message.level;
            _group.print();
        } else if (_.isArguments(message.value)) {
            _title = "Arguments (" + message.value.length + ")    " + _.map(Array.from(message.value), JSON.stringify).join('    ');
            _value = Array.from(message.value);
            _group = groupModel(_title, messageModel(_value, message.level));
            _group.isCollapsed = true;
            _group.print();
        } else if (_.isArray(message.value)) {
            _.each(message.value, function (msg) {
                _printPretty(messageModel(msg, message.level));
            });
        } else if (_.isObject(message.value) && _.has(message.value, 0) && _.isElement(message.value[0])) {
            // DOM element
            _title = "#" + message.value.get(0).id + " ." + message.value.get(0).className.split(' ').join('.');
            _value = message.value.get(0).outerHTML;
            _group = groupModel(_title, messageModel(_value, message.level));
            _group.isCollapsed = true;
            _group.print();
        } else if (!_.isString(message.value) && !_.isUndefined(message.value)) {
            _title = JSON.stringify(message.value);
            _value = message.value;
            _group = groupModel(_title, messageModel(_value, message.level));
            _group.isCollapsed = true;
            _group.isRaw = true;
            _group.print();
        } else {
            message.print();
        }
    };

    var _getStyle = function (level) {
        var levelOptions = _LEVELS[level];
        return (levelOptions) ? levelOptions.style : "";
    };

    var messageModel = function (value, level) {
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
    var groupModel = function (title, message) {
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

    var logModel = function (level, logger) {
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
                        var group = groupModel(_log.getPrefix(messagePrefix), messageModel(messageValue, _log.level));
                        group.print();
                    }
                };
            },
            setCategory: function (category) {
                _log.category = category;
            },
        };
    };

    var levels = ['warning', 'debug', 'verbose'];
    var Level = function (_levelSlug, _levelPrefix, _logger) {
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
                var _log = logModel(_levelData, _logger);
                _log.setCategory(category);
                level[slug] = _log.getPrint();
            }
        };
        level.addCategory('log');
        return level;
    };

    var loggerModel = function (_prefix) {
        var logger = {};
        logger.prefix = _prefix;
        logger.createLevel = function (slug, name) {
            return Level(slug, name, logger);
        };
        _.each(_LEVELS, function (options, key) {
            logger[key] = logger.createLevel(key, options.name);
        });
        logger.fmt = {};
        logger.fmt.groupMsg = function (title, message) {
            return groupModel(title, messageModel(message));
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
            return loggerModel(apiName);
        },
    };
});
