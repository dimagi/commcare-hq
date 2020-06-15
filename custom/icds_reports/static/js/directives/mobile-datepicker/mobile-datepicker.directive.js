/* eslint-disable */
// note: this code is mostly a direct import of https://github.com/Ankitdhir/angularjs-ios-style-datepicker
// with a few minor modifications to allow for removing the day of month and small UX tweaks
var url = hqImport('hqwebapp/js/initial_page_data').reverse;

angular.module('icdsApp').directive('mobileDatepicker', function() {
    // Runs during compile
    return {
        scope: {
            date: "=",
            minYear: "=",
            maxYear: "=",
            startMonth: "=",
            maxMonth: "="
        }, // {} = isolate, true = child, false/undefined = no change
        restrict: 'E', // E = Element, A = Attribute, C = Class, M = Comment
        templateUrl: url('icds-ng-template-mobile', 'mobile-datepicker.directive'),
        replace: true,
        link: function($scope, iElm, iAttrs, controller) {

            (function($) {

                $.fn.WSlot = function( options ) {

                    if(options=='rollTo'){
                        var args = (Array.prototype.slice.call( arguments, 1 ));
                        this.trigger(wslot_rollto,args);
                        return;
                    }

                    if(options=='get'){
                        // this.trigger('WSlot.get');
                        return this.children('div.'+class_item_selected).index();
                    }

                    if(options=='getText'){
                        // this.trigger('WSlot.get');
                        return this.children('div.'+class_item_selected).text();
                    }

                    var opts = $.extend({},$.fn.WSlot.defaults,options);

                    this.off(wslot_rollto).on(wslot_rollto,function(event,to){
                        self = $(this);
                        if(to) {
                            rollTo(self,to);
                        }
                    });

                    var style = {};
                    style['position'] = 'relative';
                    style[xform] = 'rotateY('+opts.rotation+'deg)';
                    style[xform+'-style'] = 'preserve-3d';
                    this.css(style).addClass('wslot-container');

                    var item = '';
                    if(opts.items.length) {

                        var center_index = 0;
                        if(opts.center == 'first') {
                            center_index = 0;
                        } else if(opts.center == 'last') {
                            center_index = opts.items.length - 1;
                        } else if(opts.center == 'center') {
                            center_index = parseInt(opts.items.length / 2);
                        } else if($.isNumeric(opts.center) && (opts.center >= 0) && (opts.center < opts.items.length)) {
                            center_index = opts.center;
                        } else if(opts.center >= opts.items.length) {
                            center_index = opts.items.length-1;
                        } else {
                            center_index = 0;
                        }

                        var distance = parseInt(this.height()*0.75);
                        if($.isNumeric(opts.distance)) {
                            distance = opts.distance;
                        }

                        var style = 'position: absolute;left: 0;width: 100%;height: '+opts.item_height+'px;top: 50%;margin-top: -'+Math.round(opts.item_height/2)+'px;';

                        for (var i = 0; i < opts.items.length; i++) {
                            var displayed = "";
                            if (Math.abs(i - center_index) > opts.displayed_length) {
                                displayed = "display:none;";
                            }
                            var angle = opts.angle * ( center_index - i );
                            var opacity = 0;
                            // var scale = 0.95;
                            var max_angle = opts.angle * opts.displayed_length;
                            if(Math.abs(angle) <= max_angle) {
                                opacity = 1 - (Math.abs(angle)/(max_angle*2));
                                // scale = 1 - (Math.abs(angle)/(max_angle*20));
                            }
                            var transform = 'transform:rotateX('+angle+'deg) translate3d(0,0,'+distance+'px);-webkit-transform:rotateX('+angle+'deg) translate3d(0,0,'+distance+'px);';
                            item += '<div class="wslot-item '+((i==center_index)?class_item_selected:'')+'" style="'+transform+displayed+style+'opacity:'+opacity+';">'+opts.items[i]+'</div>';
                        }

                        return this.html(item).data('cur-angle',(center_index*opts.angle))
                            .off(start).on(start, function(e) {
                                var ini = $(this);
                                ini.addClass('w-roll-touched').data('initialtouch', getEventPos(e).y);
                                return false;
                            }).off(move).on(move, function(e) {
                                var ini = $(this);
                                if (ini.is('.w-roll-touched')) {
                                    var deltaY = ini.data('initialtouch') - getEventPos(e).y;
                                    var mainAngle = parseInt(ini.data('cur-angle')) + parseInt(deltaY/2);

                                    var maxAngle = (opts.items.length - 1) * opts.angle;
                                    if (mainAngle < 0) {
                                        var excess = 0 - mainAngle;
                                        mainAngle = -(25*excess/(excess+25));
                                    } else if (mainAngle > maxAngle) {
                                        var excess = mainAngle - maxAngle;
                                        mainAngle = maxAngle + (25*excess/(excess+25));
                                    }

                                    ini.children('div').each(function () {
                                        var curr = $(this);
                                        var options = {};
                                        var currAngle = mainAngle-(curr.index()*opts.angle);
                                        options['display'] = '';
                                        if(Math.abs(currAngle) > opts.displayed_length*opts.angle) {
                                            options['display'] = 'none';
                                        }
                                        var opacity = 0;
                                        // var scale = 0.95;
                                        var max_angle = opts.angle * opts.displayed_length;
                                        if(Math.abs(currAngle) <= max_angle) {
                                            opacity = 1 - (Math.abs(currAngle)/(max_angle*2));
                                            // scale = 1 - (Math.abs(currAngle)/(max_angle*20));
                                        }
                                        options[xform] = 'rotateX('+currAngle+'deg) translateZ('+distance+'px)';
                                        options['opacity'] = opacity;
                                        curr.css(options);
                                    });
                                }
                                return false;
                            }).off(end).on(end, function(e) {
                                var ini = $(this);
                                if (ini.is('.w-roll-touched')) {
                                    var deltaY = ini.data('initialtouch') - getEventPos(e).y;

                                    var mainAngle = parseInt(ini.data('cur-angle')) + parseInt(deltaY/2);

                                    var maxAngle = (opts.items.length - 1) * opts.angle;

                                    var index = Math.round(mainAngle / opts.angle);

                                    if (mainAngle < 0) {
                                        var excess = 0 - mainAngle;
                                        mainAngle = -(25*excess/(excess+25));
                                        index = 0;
                                    } else if (mainAngle > maxAngle) {
                                        var excess = mainAngle - maxAngle;
                                        mainAngle = maxAngle + (25*excess/(excess+25));
                                        index = (opts.items.length - 1);
                                    }

                                    ini.data('cur-angle',mainAngle);

                                    rollTo(ini,index);
                                }
                                ini.removeClass('w-roll-touched')
                                return false;
                            });
                    } else {
                        return this;
                    }

                    function rollTo(objek,index){
                        if (index < 0) {
                            index = 0;
                        } else if (index >= opts.items.length) {
                            index = opts.items.length - 1;
                        }
                        var fromAngle = parseInt(objek.data('cur-angle'));
                        var toAngle = index * opts.angle;
                        var deltaAngle = toAngle - fromAngle;
                        animationStep(10,1,function(step,curStep,objek){
                            var mainAngle = easeOutQuad(curStep,fromAngle,deltaAngle,step);
                            objek.children('div').each(function () {
                                var curr = $(this);
                                var options = {};
                                var currAngle = mainAngle-(curr.index()*opts.angle);
                                options['display'] = '';
                                if(Math.abs(currAngle) > opts.displayed_length*opts.angle) {
                                    options['display'] = 'none';
                                }
                                var opacity = 0;
                                // var scale = 0.95;
                                var max_angle = opts.angle * opts.displayed_length;
                                if(Math.abs(currAngle) <= max_angle) {
                                    opacity = 1 - (Math.abs(currAngle)/(max_angle*2));
                                    // scale = 1 - (Math.abs(currAngle)/(max_angle*20));
                                }
                                options[xform] = 'rotateX('+currAngle+'deg) translateZ('+distance+'px)';
                                options['opacity'] = opacity;
                                curr.css(options);
                            });
                        },function(objek){
                            objek.children('div').each(function () {
                                var curr = $(this).removeClass(class_item_selected);
                                var options = {};
                                var currAngle = toAngle-(curr.index()*opts.angle);
                                options['display'] = '';
                                if(Math.abs(currAngle) > opts.displayed_length*opts.angle) {
                                    options['display'] = 'none';
                                }
                                var opacity = 0;
                                // var scale = 0.95;
                                var max_angle = opts.angle * opts.displayed_length;
                                if(Math.abs(currAngle) <= max_angle) {
                                    opacity = 1 - (Math.abs(currAngle)/(max_angle*2));
                                    // scale = 1 - (Math.abs(currAngle)/(max_angle*20));
                                }
                                options[xform] = 'rotateX('+currAngle+'deg) translateZ('+distance+'px)';
                                options['opacity'] = opacity;
                                curr.css(options);
                                if(currAngle == 0) {
                                    curr.addClass(class_item_selected);
                                }
                            });
                            objek.data('cur-angle',toAngle);
                            objek.trigger('WSlot.change',[index]);
                        },objek);
                    };

                };

                $.fn.WSlot.defaults = {
                    items : [],
                    center : 'first',
                    distance : 'auto',
                    displayed_length : 1,
                    angle : 30,
                    rotation : 0,
                    item_height : 20,
                };

                var xform = 'transform';
                ['webkit', 'Moz', 'O', 'ms'].every(function (prefix) {
                    var e = prefix + 'Transform';
                    if (typeof document.body.style[e] !== 'undefined') {
                        xform = e;
                    }
                });

                var start = 'touchstart mousedown';
                var move = 'touchmove mousemove';
                var end = 'touchend mouseup mouseleave';
                var wslot_rollto = 'WSlot.rollTo';
                var class_item_selected = 'wslot-item-selected';

                function animationStep(step, curStep, stepFunc, doneFunc, objek){
                    if(curStep <= step)
                    {
                        if(typeof stepFunc == 'function')
                        {
                            stepFunc(step,curStep,objek);
                        }
                        curStep = curStep+1;
                        window.requestAnimationFrame(function() {
                            animationStep(step,curStep,stepFunc,doneFunc,objek);
                        });
                    }
                    else
                    {
                        if(typeof doneFunc == 'function')
                        {
                            doneFunc(objek);
                        }
                    }
                };

                function getEventPos(e) {
                    //jquery event
                    if (e.originalEvent) {
                        // touch event
                        if (e.originalEvent.changedTouches && (e.originalEvent.changedTouches.length >= 1)) {
                            return {
                                x: e.originalEvent.changedTouches[0].pageX,
                                y: e.originalEvent.changedTouches[0].pageY
                            };
                        }
                        // mouse event
                        return {
                            x: e.originalEvent.clientX,
                            y: e.originalEvent.clientY
                        };
                    } else {
                        // touch event
                        if (e.changedTouches && (e.changedTouches.length >= 1)) {
                            return {
                                x: e.changedTouches[0].pageX,
                                y: e.changedTouches[0].pageY
                            };
                        }
                        // mouse event
                        return {
                            x: e.clientX,
                            y: e.clientY
                        };
                    }
                };

                function easeOutQuad(t, b, c, d) {
                    return -c * (t /= d) * (t - 2) + b;
                };


            })(jQuery);

            var today = $scope.date;
            var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];

            //this method returns months to be displayed corresponding to the year selected
            // if its minYear, then from months list months before startMonth is removed
            // if its current year then from months list months that comes after the current month are removed
            var getAvailableMonthsForSelectedYear = function () {
                return ($scope.date.getFullYear() === $scope.minYear) ? months.slice($scope.startMonth - 1) :
                        (($scope.date.getFullYear() === $scope.maxYear) ?
                            months.slice(0, $scope.maxMonth) : months);
            };

            // this method returns which month to be shown at the center of datepicker
            // it is picked from items array.
            // eg: minyear=2017 and startMonth = 3. So to display the "month of may" center should be 3rd element
            // (position 2 in array) in months array. $scope.date.getMonth() returns 4 for may.
            // we should decrease (startMonth-1) elements for proper value
            var getCenterMonth = function () {
                var centerMonth = $scope.date.getMonth();
                if ($scope.date.getFullYear() === $scope.minYear) {
                    centerMonth = $scope.date.getMonth()- ($scope.startMonth - 1);
                } else if ($scope.date.getFullYear() === $scope.maxYear) {
                    if ($scope.date.getMonth() > $scope.maxMonth - 1) {
                        centerMonth = $scope.maxMonth - 1;
                    }
                }
                return centerMonth;
            };

            $('.month').WSlot({
                items:getAvailableMonthsForSelectedYear(),
                center:getCenterMonth(),
                angle:30,
                distance:'auto',
                displayed_length:1,
                rotation:0
            }).on('WSlot.change',function(e,index){
                initDate(index,parseInt($('.year').WSlot('getText')),$('.day').WSlot('get'));
                updateText();
            });

            initDate(today.getMonth(),today.getFullYear(),today.getDate()-1);

            var years = [];
            for (var i = parseInt($scope.minYear); i <= parseInt($scope.maxYear); i++) {
                years.push(i);
            };
            $('.year').WSlot({
                items:years,
                center:years.indexOf(today.getFullYear()),
                angle:30,
                distance:'auto',
                displayed_length:1,
                rotation:0
            }).on('WSlot.change',function(e,index){
                initDate(parseInt($('.month').WSlot('get')),parseInt($('.year').WSlot('getText')),$('.day').WSlot('get'));
                updateText();
                $('.month').WSlot({
                    items: getAvailableMonthsForSelectedYear(),
                    center: getCenterMonth(),
                    angle:30,
                    distance:'auto',
                    displayed_length:1,
                    rotation:0
                });
                updateText();
            });

            function updateText() {
                var dd = ('0'+($('.day').WSlot('get')+1)).slice(-2);
                var mm = ('0'+($('.month').WSlot('get')+1)).slice(-2);
                if ($scope.date.getFullYear() === $scope.minYear) {
                    mm = ('0'+($('.month').WSlot('get')+$scope.startMonth)).slice(-2);
                } else if ($scope.date.getFullYear() === $scope.maxYear) {
                    if (parseInt($('.month').WSlot('get')) > ($scope.maxMonth - 1)) {
                        mm = '0'+ $scope.maxMonth;
                    }
                }
                var yyyy = $('.year').WSlot('getText');
                var todaystring = yyyy+'-'+mm+'-'+dd;
                $scope.date = new Date(todaystring);
                $scope.$apply();
                $scope.$emit('date_picked',{'info' : $scope.date });
            }

            $scope.$on('reset_date', function() {
                // upon reset center is set to current year and current month
                $scope.date = new Date($scope.maxYear, ($scope.maxMonth - 1));
                $('.year').WSlot({
                    items:years,
                    center:years.indexOf($scope.date.getFullYear()),
                    angle:30,
                    distance:'auto',
                    displayed_length:1,
                    rotation:0
                });
                $('.month').WSlot({
                    items:getAvailableMonthsForSelectedYear(),
                    center:$scope.date.getMonth(),
                    angle:30,
                    distance:'auto',
                    displayed_length:1,
                    rotation:0
                });
            });

            function initDate(month,year,selected) {
                var totalDay = daysInMonth(month,year);
                var days = [];
                for (var i = 1; i <= totalDay; i++) {
                    days.push(i);
                };
                $('.day').empty().WSlot({
                    items:days,
                    center:selected,
                    angle:30,
                    distance:'auto',
                    displayed_length:1,
                    rotation:0
                }).off('WSlot.change').on('WSlot.change',function(e,index){
                    updateText();
                });
            }

            function daysInMonth(month,year) {
                return new Date(year, month+1, 0).getDate();
            }
        }
    };
});
