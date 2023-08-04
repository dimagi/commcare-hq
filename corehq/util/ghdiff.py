# We just needed a subset of https://github.com/kilink/ghdiff/blob/master/src/ghdiff.py,
# so we have copied the required code.
# It also helps us in getting rid of 2 dependencies

"""
The MIT License (MIT)

Copyright (c) 2011-2016 Patrick Strawderman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import difflib
import xml

default_css = """\
<style type="text/css">
    .diff {
        border: 1px solid #cccccc;
        background: none repeat scroll 0 0 #f8f8f8;
        font-family: 'Bitstream Vera Sans Mono','Courier',monospace;
        font-size: 12px;
        line-height: 1.4;
        white-space: normal;
        word-wrap: break-word;
    }
    .diff div:hover {
        background-color:#ffc;
    }
    .diff .control {
        background-color: #eaf2f5;
        color: #999999;
    }
    .diff .insert {
        background-color: #ddffdd;
        color: #000000;
    }
    .diff .insert .highlight {
        background-color: #aaffaa;
        color: #000000;
    }
    .diff .delete {
        background-color: #ffdddd;
        color: #000000;
    }
    .diff .delete .highlight {
        background-color: #ffaaaa;
        color: #000000;
    }
</style>
"""


def escape(text):
    return xml.sax.saxutils.escape(text, {" ": "&nbsp;"})


def diff(a, b, n=3, css=True):
    if isinstance(a, str):
        a = a.splitlines()
    if isinstance(b, str):
        b = b.splitlines()
    return colorize(list(difflib.unified_diff(a, b, n=n)), css=css)


def colorize(diff, css=True):
    css = default_css if css else ""
    return css + "\n".join(_colorize(diff))


def _colorize(diff):
    if isinstance(diff, str):
        lines = diff.splitlines()
    else:
        lines = diff
    lines.reverse()
    while lines and not lines[-1].startswith("@@"):
        lines.pop()
    yield '<div class="diff">'
    while lines:
        line = lines.pop()
        klass = ""
        if line.startswith("@@"):
            klass = "control"
        elif line.startswith("-"):
            klass = "delete"
            if lines:
                _next = []
                while lines and len(_next) < 2:
                    _next.append(lines.pop())
                if _next[0].startswith("+") and (
                        len(_next) == 1 or _next[1][0] not in ("+", "-")):
                    aline, bline = _line_diff(line[1:], _next.pop(0)[1:])
                    yield '<div class="delete">-%s</div>' % (aline,)
                    yield '<div class="insert">+%s</div>' % (bline,)
                    if _next:
                        lines.append(_next.pop())
                    continue
                lines.extend(reversed(_next))
        elif line.startswith("+"):
            klass = "insert"
        yield '<div class="%s">%s</div>' % (klass, escape(line),)
    yield "</div>"


def _line_diff(a, b):
    aline = []
    bline = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if tag == "equal":
            aline.append(escape(a[i1:i2]))
            bline.append(escape(b[j1:j2]))
            continue
        aline.append('<span class="highlight">%s</span>' % (escape(a[i1:i2]),))
        bline.append('<span class="highlight">%s</span>' % (escape(b[j1:j2]),))
    return "".join(aline), "".join(bline)
