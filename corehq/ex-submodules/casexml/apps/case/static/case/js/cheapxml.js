/* Library for generating xml with a JQuery-like syntax
        Usage:

        var $ = cheapxml.$,
            foodXML = $('<food/>').append(
                 $('<fruit/>'),
                 $('<grains/>')
             );
        console.log(foodXML.serialize());

*/
hqDefine("case/js/cheapxml",[

],function () {
    var Node = function (xmlTag) {
        var self = {};
        var tag = /^<(\w+)\/>$/.exec(xmlTag)[1],
            attributes = {},
            children = [];

        self.attr = function (attribs) {
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
        self.append = function () {
            var i;
            for (i = 0; i < arguments.length; i += 1) {
                children.push(arguments[i]);
            }
            return this;
        };
        self.appendTo = function (that) {
            that.append(this);
            return this;
        };
        self.text = function (text) {
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
        self.is = function (selector) {
            if (selector === ':parent') {
                return children || children.length;
            }
        };
        self.serialize = function (stream) {
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
        self.toString = function () {
            return this.serialize();
        };

        return self;
    };

    return {
        $: Node,
    };
});



