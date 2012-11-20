/*  Popout Bootstrap Plugin
*   ------------------------
*   Designed for CommCare HQ. Copyright 2012 Dimagi, Inc.
*
*   This extends Twitter Bootstrap's popover plugin to display the popover absolutely positioned in the page.
*   It gets around the issue with popovers in datatable's scrollable headers.
*
*/

!function ($) {

    "use strict"; // jshint ;_;

    /* POPOUT PUBLIC CLASS DEFINITION
     * =============================== */

    var Popout = function (element, options) {
        this.init('popout', element, options)
    }

    /* NOTE: POPOUT EXTENDS BOOTSTRAP-POPOVER.js
     ========================================== */

    Popout.prototype = $.extend({}, $.fn.popover.Constructor.prototype, {

        constructor: Popout

        , show: function () {
            var $tip
                , inside
                , pos
                , actualWidth
                , actualHeight
                , placement
                , tp
                , triggerOffset

            if (this.hasContent() && this.enabled) {
                $tip = this.tip()
                this.setContent()

                if (this.options.animation) {
                    $tip.addClass('fade')
                }

                placement = typeof this.options.placement == 'function' ?
                    this.options.placement.call(this, $tip[0], this.$element[0]) :
                    this.options.placement

                inside = /in/.test(placement)

                $tip
                    .detach()
                    .css({ top: 0, left: 0, display: 'block', position: 'absolute' })

                $(this.options.container).append($tip)

                pos = this.getPosition(inside)

                actualWidth = $tip[0].offsetWidth
                actualHeight = $tip[0].offsetHeight

                triggerOffset = this.$element.offset();
                pos.top = triggerOffset.top
                pos.left = triggerOffset.left

                switch (inside ? placement.split(' ')[1] : placement) {
                    case 'bottom':
                        tp = {top: pos.top + pos.height, left: pos.left + pos.width / 2 - actualWidth / 2}
                        break
                    case 'top':
                        tp = {top: pos.top - actualHeight, left: pos.left + pos.width / 2 - actualWidth / 2}
                        break
                    case 'left':
                        tp = {top: pos.top + pos.height / 2 - actualHeight / 2, left: pos.left - actualWidth}
                        break
                    case 'right':
                        tp = {top: pos.top + pos.height / 2 - actualHeight / 2, left: pos.left + pos.width}
                        break
                }

                $tip
                    .offset(tp)
                    .addClass(placement)
                    .addClass('in')

            }
        }
    })

    /* POPOUT PLUGIN DEFINITION
     * ======================= */

    $.fn.popout = function (option) {
        return this.each(function () {
            var $this = $(this)
                , data = $this.data('popout')
                , options = typeof option == 'object' && option
            if (!data) $this.data('popout', (data = new Popout(this, options)))
            if (typeof option == 'string') data[option]()
        })
    }

    $.fn.popout.Constructor = Popout

    $.fn.popout.defaults = $.extend({} , $.fn.popover.defaults, {
        container: 'body'
    })

}(window.jQuery);