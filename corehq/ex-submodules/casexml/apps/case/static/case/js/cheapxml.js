var cheapxml = {
    /* Library for generating xml with a JQuery-like syntax
        Usage:

        var $ = cheapxml.$,
            foodXML = $('<food/>').append(
                 $('<fruit/>'),
                 $('<grains/>')
             );
        console.log(foodXML.serialize());

    */
    $: (function () {
        'use strict';
        var Node = function (xmlTag) {
            var tag = /^<(\w+)\/>$/.exec(xmlTag)[1],
                attributes = {},
                children = [];

            this.attr = function (attribs) {
                var a;
                if (typeof attribs === 'object') {
                    for (a in attribs) {
                        if (attribs.hasOwnProperty(a)) {
                            attributes[a] = attribs[a];
                        }
                    }
                    return this;
                } else {
                    a = attribs;
                    return attributes[a];
                }
            };
            this.append = function () {
                var i;
                for (i = 0; i < arguments.length; i += 1) {
                    children.push(arguments[i]);
                }
                return this;
            };
            this.appendTo = function (that) {
                that.append(this);
                return this;
            };
            this.text = function (text) {
                if (text !== undefined) {
                    children = text;
                    return this;
                } else if (typeof children === 'string') {
                    return children;
                } else {
                    // fail silently?
                    return '';
                }
            };
            this.is = function (selector) {
                if (selector === ':parent') {
                    return children || children.length ? true : false;
                }
            };
            this.serialize = function (stream) {
                var out = stream || [],
                    a,
                    i;
                out.push('<');
                out.push(tag);
                for (a in attributes) {
                    if (attributes.hasOwnProperty(a)) {
                        out.push(' ');
                        out.push(a);
                        out.push('="');
                        out.push(attributes[a]);
                        out.push('"');
                    }
                }
                if (children === '' || children.length === 0) {
                    out.push('/>');
                } else {
                    out.push('>');
                    if (typeof children === 'string') {
                        out.push(children);
                    } else {
                        for (i = 0; i < children.length; i += 1) {
                            children[i].serialize(out);
                        }
                    }
                    out.push('</');
                    out.push(tag);
                    out.push('>');
                }
                if (stream === undefined) {
                    return out.join('');
                }
            };
            this.toString = function () {
                return this.serialize();
            };
        };
        return function (tag) {
            return new Node(tag);
        };
    }()),
};