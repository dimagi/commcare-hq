'use strict';
/**
 * NOTE: MONKEYPATCHED to support form clicks and other actions
 *
 * Original from:
 * @fileoverview dragscroll - scroll area by dragging
 * @version 0.0.6
 *
 * @license MIT, see http://github.com/asvd/intence
 * @copyright 2015 asvd <heliosframework@gmail.com>
 */

hqDefine("cloudcare/js/preview_app/dragscroll", ["jquery"], function ($) {
    var _window = window;
    var _document = document;
    var mousemove = 'mousemove';
    var mouseup = 'mouseup';
    var mousedown = 'mousedown';
    var EventListener = 'EventListener';
    var addEventListener = 'add' + EventListener;
    var removeEventListener = 'remove' + EventListener;

    var dragged = [];
    var reset = function (i, el) {
        for (i = 0; i < dragged.length;) {
            el = dragged[i++];
            el = el.container || el;
            el[removeEventListener](mousedown, el.md, 0);
            _window[removeEventListener](mouseup, el.mu, 0);
            _window[removeEventListener](mousemove, el.mm, 0);
        }

        // cloning into array since HTMLCollection is updated dynamically
        dragged = [].slice.call(_document.getElementsByClassName('dragscroll'));
        for (i = 0; i < dragged.length;) {
            (function (el, lastClientX, lastClientY, pushed, scroller, cont) {
                (cont = el.container || el)[addEventListener](
                    mousedown,
                    cont.md = function (e) {
                        if (!el.hasAttribute('nochilddrag') ||
                            _document.elementFromPoint(
                                e.pageX, e.pageY
                            ) === cont
                        ) {
                            pushed = 1;
                            lastClientX = e.clientX;
                            lastClientY = e.clientY;

                            // monkeypatch
                            if (!($(e.srcElement).hasClass('form-control') || $(e.target).hasClass('form-control'))) {
                                e.preventDefault();
                                $('.form-control').blur();
                            }

                        }
                    }, 0
                );

                _window[addEventListener](
                    mouseup, cont.mu = function () {pushed = 0;}, 0
                );

                _window[addEventListener](
                    mousemove,
                    cont.mm = function (e) {
                        if (pushed) {
                            (scroller = el.scroller || el).scrollLeft -=
                                (- lastClientX + (lastClientX = e.clientX));
                            scroller.scrollTop -=
                                (- lastClientY + (lastClientY = e.clientY));
                        }
                    }, 0
                );
            })(dragged[i++]);
        }
    };

    $(function () {
        reset();
    });
});

