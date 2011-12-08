/*
    The below work is licensed under Creative Commons GNU LGPL License.

    Original work:

    License:     http://creativecommons.org/licenses/LGPL/2.1/
    Author:      Stefan Goessner/2006
    Web:         http://goessner.net/ 

    Modifications made:

    Version:     0.9-p5
    Description: Restructured code, JSLint validated (no strict whitespaces),
                 added handling of empty arrays, empty strings, and int/floats values.
    Author:      Michael Scholer/2008-01-29
    Web:         http://michael.hinnerup.net/blog/2008/01/26/converting-json-to-xml-and-xml-to-json/
    
    Version:     0.9.1
    Description: Changed DOM XML to E4X XML.  
    Author:      Cory Zue (czue@dimagi.com)/2010-05-29
    Web:         http://www.dimagi.com/
*/

// this gets used when a text field has both attributes and a text value:
// <myvar a="3">bcd</myvar> ==> {"myvar": {"@a": 3, "#text": "bcd"}
var VALUE_TAG = "#text";
// this gets used to specify the root object's name
// at a top level:
// <myvar a="3"><b>cd</b></myvar> ==> {"#type": "myvar", "@a": 3, "b": "cd"}
var ROOT_TAG = "#type";

/*global alert */
var e4xmlJsonClass = {
    // abstract out the logging functionality.  it's not beautiful, but 
    // this at leasts provides a single point to change it (you still
    // have to edit the code, unfortunately)
    log_to_couch: log,
    log_to_console: function (x) {
        try {
            console.log(x);
        } catch (err) {
            console.log("" + x);
        }
    },
    log_func: this.log_to_couch,
    // log_func: this.log_to_console,
    
    hello: function() {
        this.log_func("hello world!");
    },
    
    // Param "xml": E4X XML object
    // Returns:     JavaScript object
    xml2obj: function(xml) {
        var obj = this.toObj(xml);
        obj[ROOT_TAG] = xml.name().localName;
        return obj
    },

    // Param "xml": E4X XML object
    // Param "tab": Tab or indent string for pretty output formatting omit or use empty string "" to supress.
    // Returns:     JSON string
    xml2json: function(xml, tab) {
        var obj = this.xml2obj(xml);
        var json = this.toJson(obj, xml.name().localName, "\t");
        if (!tab) tab = "";
        return "{\n" + tab + (tab ? json.replace(/\t/g, tab) : json.replace(/\t|\n/g, "")) + "\n}";
    },

    // Param "o":   JavaScript object
    // Param "tab": tab or indent string for pretty output formatting omit or use empty string "" to supress.
    // Returns:     XML string
    json2xml: function(o, tab) {
        var toXml = function(v, name, ind) {
            var xml = "";
            var i, n;
            if (v instanceof Array) {
                if (v.length === 0) {
                    xml += ind + "<"+name+">__EMPTY_ARRAY_</"+name+">\n";
                }
                else {
                    for (i = 0, n = v.length; i < n; i += 1) {
                        var sXml = ind + toXml(v[i], name, ind+"\t") + "\n";
                        xml += sXml;
                    }
                }
            }
            else if (typeof(v) === "object") {
                var hasChild = false;
                xml += ind + "<" + name;
                var m;
                for (m in v) if (v.hasOwnProperty(m)) {
                    if (m.charAt(0) === "@") {
                        xml += " " + m.substr(1) + "=\"" + v[m].toString() + "\"";
                    }
                    else {
                        hasChild = true;
                    }
                }
                xml += hasChild ? ">" : "/>";
                if (hasChild) {
                    for (m in v) if (v.hasOwnProperty(m)) {
                        if (m === "#text") {
                            xml += v[m];
                        }
                        else if (m === "#cdata") {
                            xml += "<![CDATA[" + v[m] + "]]>";
                        }
                        else if (m.charAt(0) !== "@") {
                            xml += toXml(v[m], m, ind+"\t");
                        }
                    }
                    xml += (xml.charAt(xml.length - 1) === "\n" ? ind : "") + "</" + name + ">";
                }
            }
            else {
                if (v.toString() === "\"\"" || v.toString().length === 0) {
                    xml += ind + "<" + name + ">__EMPTY_STRING_</" + name + ">";
                } 
                else {
                    xml += ind + "<" + name + ">" + v.toString() + "</" + name + ">";
                }
            }
            return xml;
        };
        var xml = "";
        var m;
        for (m in o) if (o.hasOwnProperty(m)) {
            xml += toXml(o[m], m, "");
        }
        return tab ? xml.replace(/\t/g, tab) : xml.replace(/\t|\n/g, "");
    },

    logObj: function(obj) {
        for (var prop in obj) {
            val = obj[prop];
            if (val) { 
                if (val != obj) {
                    this.logObj(val);
                }
            }
        }
    }, 
    // Internal methods
    toObj: function(xml, expectedNamespace) {
        var attributes = xml.@*;
            
        var actualNamespace = xml.name().uri;
        var addNamespace = (actualNamespace && actualNamespace !== expectedNamespace);
        
        // base case, a simple node
        if (attributes.length() == 0 && !this.hasChildren(xml) && !addNamespace) {
            return (xml || "").toString();
        }
        
        var o = {};
        
        if (addNamespace) {
            o["@" + "xmlns"] = actualNamespace;
        }
        
        // process attributes
        if (attributes.length() > 0) {
            for (var i = 0; i < attributes.length(); i++) {
                o["@" + attributes[i].name().localName] = (attributes[i] || "").toString();
            }
        }
        
        // process children
        if (this.hasChildren(xml)) {
            var children = xml.*;
            
            for (var i = 0; i < children.length(); i++) {
                if (xml.*::[children[i].name().localName].length() > 1) {
                    // there was more than one of these elements.  Make it a list.
                    if (!o[children[i].name().localName]) {
                        o[children[i].name().localName] = []; 
                    }
                    o[children[i].name().localName][o[children[i].name().localName].length] = this.toObj(children[i], actualNamespace);
                } else {
                    o[children[i].name().localName] = this.toObj(children[i], actualNamespace);
                }
            }
        } 
        else {
            // this had attributes, but no children.  Default the value to #text
            o[VALUE_TAG] = (xml || "").toString();
        }
        
        return o;
        
    },
    hasChildren: function(xml) {
        if (xml.*.length() > 0 && !(xml.*.length() == 1 && !xml.*[0].name())) {
            return true;
        }
        return false;            
    }, 
    toJson: function(o, name, ind) {
        var json = name ? ("\"" + name + "\"") : "";
        if (o === "[]") {
            json += (name ? ":[]" : "[]");
        } 
        else if (o instanceof Array) {
            var n, i;
            for (i = 0, n = o.length; i < n; i += 1) {
                o[i] = this.toJson(o[i], "", ind + "\t");
            }
            json += (name ? ":[" : "[") + (o.length > 1 ? ("\n" + ind + "\t" + o.join(",\n" + ind + "\t") + "\n" + ind) : o.join("")) + "]";
        }
        else if (o === null) {
            json += (name && ":") + "null";
        }
        else if (typeof(o) === "object") {
            var arr = [];
            var m;
            for (m in o) if (o.hasOwnProperty(m)) {
                arr[arr.length] = this.toJson(o[m], m, ind + "\t");
            }
            json += (name ? ":{" : "{") + (arr.length > 1 ? ("\n" + ind + "\t" + arr.join(",\n" + ind + "\t") + "\n" + ind) : arr.join("")) + "}";
        }
        else if (typeof(o) === "string") {
            o = o.toString();
            var objRegExp  = /(^-?\d+\.?\d*$)/;
            if (objRegExp.test(o)) {
                // int or float
                json += (name && ":") + o;
            }
            else {
                json += (name && ":") + "\"" + o + "\"";
            }
        }
        else {
            json += (name && ":") + o.toString();
        }
        return json;
    },
    innerXml: function(node) {
        var s = "";
        if ("innerHTML" in node) {
            s = node.innerHTML;
        }
        else {
            var asXml = function(n) {
                var s = "", i;
                if (n.nodeType === 1) {
                    s += "<" + n.nodeName;
                    for (i = 0; i < n.attributes.length; i += 1) {
                        s += " " + n.attributes[i].nodeName + "=\"" + (n.attributes[i].nodeValue || "").toString() + "\"";
                    }
                    if (n.firstChild) {
                        s += ">";
                        for (var c = n.firstChild; c; c = c.nextSibling) {
                            s += asXml(c);
                        }
                        s += "</" + n.nodeName + ">";
                    }
                    else {
                        s += "/>";
                    }
                }
                else if (n.nodeType === 3) {
                    s += n.nodeValue;
                }
                else if (n.nodeType === 4) {
                    s += "<![CDATA[" + n.nodeValue + "]]>";
                }
                return s;
            };
            for (var c = node.firstChild; c; c = c.nextSibling) {
                s += asXml(c);
            }
        }
        return s;
    },
    escape: function(txt) {
        return txt.replace(/[\\]/g, "\\\\").replace(/[\"]/g, '\\"').replace(/[\n]/g, '\\n').replace(/[\r]/g, '\\r');
    },
    removeWhite: function(e) {
        e.normalize();
        var n;
        for (n = e.firstChild; n; ) {
            if (n.nodeType === 3) {
                // text node
                if (!n.nodeValue.match(/[^ \f\n\r\t\v]/)) {
                    // pure whitespace text node
                    var nxt = n.nextSibling;
                    e.removeChild(n);
                    n = nxt;
                }
                else {
                    n = n.nextSibling;
                }
            }
            else if (n.nodeType === 1) {
                // element node
                this.removeWhite(n);
                n = n.nextSibling;
            }
            else {
                // any other node
                n = n.nextSibling;
            }
        }
        return e;
    }
};

exports.e4xmlJsonClass = e4xmlJsonClass;
