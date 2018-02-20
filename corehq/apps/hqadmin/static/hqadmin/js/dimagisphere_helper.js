/* globals hqDefine */
hqDefine('hqadmin/js/dimagisphere_helper', function () {
    var dimagisphere = (function() {
        var self = {};
    
        self.formData = {
            totalFormsByCountry: {},  // keeps track of totals per country
            recentFormsByCountry: {},  // keeps track of "active" per country - from the last second
            maxFormsByCountry: 0, // most forms that any single country has submitted
            totalFormsByDomain: {}, // keeps track of totals per domain
            domainToCountry: {},
        };
    
        self.addData = function (dataItem) {
            /**
             * Adds data to self.formData. Returns whether anything was done.
             */
            dimagisphere.formData.domainToCountry[dataItem.domain] = dataItem.country;
            var currentDomainCount = dimagisphere.formData.totalFormsByDomain[dataItem.domain] || 0;
            currentDomainCount += 1;
            dimagisphere.formData.totalFormsByDomain[dataItem.domain] = currentDomainCount;
            if (dataItem.country) {
                // update totals
                var currentCount = self.formData.totalFormsByCountry[dataItem.country] || 0;
                currentCount += 1;
                self.formData.totalFormsByCountry[dataItem.country] = currentCount;
                if (currentCount > self.formData.maxFormsByCountry) {
                    self.formData.maxFormsByCountry = currentCount;
                }
                // update active
                var activeCount = self.formData.recentFormsByCountry[dataItem.country] || 0;
                self.formData.recentFormsByCountry[dataItem.country] = activeCount + 1;
                return true;
            }
            return false;
        };
    
        var FAKE_DOMAINS = {
            'dimagi': 'United States of America',
            'unicef': 'Nigeria',
            'mvp': 'Ethiopia',
            'dsi': 'India',
            'icds': 'India',
            'tula': 'Guatemala',
        };
    
        self.generateRandomItem = function () {
            // just return a random item from FAKE_DOMAINS
            // http://stackoverflow.com/questions/2532218/pick-random-property-from-a-javascript-object
            var domains = Object.keys(FAKE_DOMAINS);
            var randomDomain = domains[domains.length * Math.random() << 0];
            return {
                domain: randomDomain,
                country: FAKE_DOMAINS[randomDomain],
            };
        };
        return self;
    })();
    
    $(function() {
        var filter = {},
            initial_page_data = $("body").data();
    
        // courtesy of http://colorbrewer2.org/
        var COUNTRY_COLORS = ['#edf8fb','#b2e2e2','#66c2a4','#2ca25f','#006d2c'];
        var COUNTRY_ACTIVE_COLORS = ['#fef0d9','#fdcc8a','#fc8d59','#e34a33','#b30000'];
        var ws4redis = WS4Redis({
            uri: initial_page_data.uri + 'form-feed?subscribe-broadcast',
            receive_message: receiveMessage,
            heartbeat_msg: initial_page_data.heartbeatMessage,
        });
    
        // in tv mode we don't show domains in the graph but just countries
        var tvmode = initial_page_data.tvmode;
        var chartSourceData = tvmode ? dimagisphere.formData.totalFormsByCountry : dimagisphere.formData.totalFormsByDomain;
    
        function addDataToMap(msgObj) {
            colorAll();
            // this removes from active after a bit of time
            window.setTimeout(function () {
                dimagisphere.formData.recentFormsByCountry[msgObj.country] -= 1;
            }, 1000);
        }
    
        // receive a message though the Websocket from the server
        function receiveMessage(msg) {
            var msgObj = JSON.parse(msg);
            // var renderedMsg = '<strong>' + msgObj.username + '</strong>: ' + msgObj.message;
    
            dimagisphere.addData(msgObj);
            if (msgObj.country) {
                addDataToMap(msgObj);
            }
            // add data to chart
            if (chart !== undefined) {
                chartData.datum(formatChartData(chartSourceData)).call(chart);
    
                // when the bar for a domain is clicked on, we can filter on that domain
                // isn't in use with just this one chart and the map, but maybe if there are other charts added
                d3.selectAll(".discreteBar").on('click', function(d) {
                    if (filter.domain && filter.domain === d.domain) {
                        filter.domain = null;
                    } else {
                        filter.domain = d.domain;
                    }
                });
                try {
                    nv.utils.windowResize(chart.update);
                } catch (err) {
                    // if the chart is being updated frequently then this can fail so just ignore it for now
                }
            }
        }
    
        // charts
        var chart, chartData;
        nv.addGraph(function() {
            chart = nv.models.discreteBarChart()
                .x(function(d) { return d.domain; })
                .y(function(d) { return d.count; })
                .staggerLabels(true)
                .tooltips(false)
                .showValues(true)
                .transitionDuration(350)
            ;
            chartData = d3.select('#chart svg').datum(formatChartData(chartSourceData));
            chartData.call(chart);
            nv.utils.windowResize(chart.update);
            return chart;
        });
        function formatChartData(data) {
            var values = $.map(data, function (count, domain) { return {'domain': domain, 'count': count}; });
            if (filter.country) {
                values = values.filter(function(obj) {
                    if (tvmode) {
                        return obj.domain === filter.country;
                    } else {
                        return dimagisphere.formData.domainToCountry[obj.domain] === filter.country;
                    }
                });
            }
            // can uncomment the below line to sort by descending count (this causes colors to change over time)
            // values.sort(function (a, b) { return b.count - a.count; });
            return [{
                key: "Submissions by Domain",
                values: values,
            }];
        }
    
        var countriesGeo;
        // A lot of the styling work here is modeled after http://leafletjs.com/examples/choropleth.html
        var map = L.map('map').setView([0, 0], 2);
        var mapId = 'mapbox.dark';
        L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
            maxZoom: 10,
            id: mapId,
            accessToken: initial_page_data.token,
        }).addTo(map);
    
        function getColor(featureId) {
            var count = dimagisphere.formData.totalFormsByCountry[featureId];
            if (!count) {
                return COUNTRY_COLORS[0];
            }
            var activeCount = dimagisphere.formData.recentFormsByCountry[featureId];
            if (!activeCount) {
                var pct = count / dimagisphere.formData.maxFormsByCountry;
                var index = Math.min(Math.floor(pct * COUNTRY_COLORS.length), COUNTRY_COLORS.length - 1);
    
                return COUNTRY_COLORS[index];
            }
            else {
                // these values are adjusted slightly to use all 5 colors, not leaving out the first color
                var activeIndex = Math.min(activeCount, COUNTRY_ACTIVE_COLORS.length);
                return COUNTRY_ACTIVE_COLORS[activeIndex - 1];
            }
        }
    
        function getOpacity(featureId) {
            if (dimagisphere.formData.totalFormsByCountry[featureId]) {
                if (filter.country != null) {
                    if (featureId === filter.country) {
                        return .9;
                    } else {
                        return .3;
                    }
                }
                return .9;
            } else {
                return 0;
            }
        }
    
        function style(feature) {
            return {
                fillColor: getColor(feature.properties.name),
                weight: 2,
                opacity: 1,
                color: 'white',
                dashArray: '3',
                fillOpacity: getOpacity(feature.properties.name),
            };
        }
    
        // highlights
        function highlightFeature(e) {
            var layer = e.target;
            layer.setStyle({
                weight: 4,
                color: '#002c5f',
                dashArray: '',
            });
            if (!L.Browser.ie && !L.Browser.opera) {
                layer.bringToFront();
            }
            info.update(layer.feature.properties);
        }
    
        function resetHighlight(e) {
            countriesGeo.resetStyle(e.target);
            info.update();
        }
    
        function onEachFeature(feature, layer) {
            layer.on({
                mouseover: highlightFeature,
                mouseout: resetHighlight,
                click: function() {
                    // when a country is clicked on, we filter by country name
                    if (filter.country === layer.feature.properties.name) {
                        filter.country = null;
                    } else {
                        filter.country = layer.feature.properties.name;
                        // show the name in text somewhere to avoid scanning the map? maybe in the top right?
                    }
                    chartData.datum(formatChartData(chartSourceData)).call(chart);
                    countriesGeo.setStyle(style);
                },
            });
        }
    
        // info control
        var info = L.control();
        info.onAdd = function (map) {
            this._div = L.DomUtil.create('div', 'map-info');
            this.update();
            return this._div;
        };
    
        // method that we will use to update the control based on feature properties passed in
        info.update = function (props) {
            function _getInfoContent(countryName) {
                var formCount = dimagisphere.formData.totalFormsByCountry[countryName];
                var message = formCount ? formCount + ' forms' : 'no data yet';
                return '<b>' + countryName + '</b>: ' + message;
            }
            this._div.innerHTML = (props ? _getInfoContent(props.name) : 'Hover over a country');
        };
        info.addTo(map);
    
        // todo: should probably be getting this from somewhere else and possibly not on every page load.
        $.getJSON('https://raw.githubusercontent.com/dimagi/world.geo.json/master/countries.geo.json', function (data) {
            countriesGeo = L.geoJson(data, {style: style, onEachFeature: onEachFeature}).addTo(map);
        });
    
        function colorAll() {
            if (countriesGeo !== undefined) {
                countriesGeo.setStyle(style);
                map.removeControl(legend);
                legend.addTo(map);
            }
        }
    
        // update all every 5 seconds in case no activity (this is just to clear active state)
        window.setInterval(colorAll, 5000);
    
        // add a legend
        var legend = L.control({position: 'bottomleft'});
    
        var createLegend = function (map) {
            var div = L.DomUtil.create('div', 'info legend');
    
            var activeCountValues = COUNTRY_ACTIVE_COLORS.map(function(e, i) {
                return i+1;
            });
    
            // get the upper bounds for each bucket
            var countValues = COUNTRY_COLORS.map(function(e, i) {
                var bound = dimagisphere.formData.maxFormsByCountry * (i+1) / COUNTRY_COLORS.length;
                return Math.max(0, (i < COUNTRY_COLORS.length -1 && Math.floor(bound) === bound) ? bound - 1 : Math.floor(bound));
            });
    
            // only include legend items that are actually used right now
            // when there is a low number of maxForms, they may not all be included
            var indicesToRemove = [];
            var colors = COUNTRY_COLORS.filter(function(elem, index) {
                if (countValues[index] <= 0 || (index > 0 && countValues[index] == countValues[index-1])) {
                    indicesToRemove.push(index);
                    return false;
                } else {
                    return true;
                }
            });
    
            countValues = countValues.filter(function(elem, index) {
                return indicesToRemove.indexOf(index) <= -1;
            });
    
            div.innerHTML += '<p>Recent Forms</p>';
    
            // loop through our active form values and generate a label with a colored square for each value
            for (var i = 0; i < activeCountValues.length; i++) {
                div.innerHTML +=
                    '<i style="background:' + COUNTRY_ACTIVE_COLORS[i] + '"></i> ' +
                    activeCountValues[i] + (activeCountValues[i + 1] ? '<br>' : "+");
            }
    
            div.innerHTML += '<div class="padding"></div>';
    
            div.innerHTML += '<p>All Forms Since Opening</p>' +
                             '<i style="background:' + 'black' + '"></i> ' + '0' + '<br>'; 
    
            // loop through our form count intervals and generate a label with a colored square for each interval
            for (var i = 0; i < countValues.length; i++) {
                div.innerHTML += '<i style="background:' + colors[i] + '"></i> ';
                if (countValues[i-1] !==  undefined) {
                    if (countValues[i-1] +1 < countValues[i]) {
                        div.innerHTML += (countValues[i-1] + 1) + '&ndash;';
                    }
                } else if (countValues[i] > 1) {
                    div.innerHTML += '1&ndash;';
                }
                div.innerHTML += countValues[i] + '<br>';
            }
    
            return div;
        };
    
        legend.onAdd = createLegend;
        legend.addTo(map);
    
        // simulation controls
        var simulationOn = false;
        var controlButton = $('#controlButton');
        function setPauseButton() {
            controlButton.children('span').removeClass('fa-play').addClass('fa-pause');
        }
        function setPlayButton() {
            controlButton.children('span').removeClass('fa-pause').addClass('fa-play');
        }
        function simulateForms() {
            if (simulationOn) {
                receiveMessage(JSON.stringify(dimagisphere.generateRandomItem()));
                window.setTimeout(simulateForms, 1200);
            }
        }
        controlButton.click(function () {
            if (!simulationOn) {
                simulationOn = true;
                setPauseButton();
                simulateForms();
            } else {
                simulationOn = false;
                setPlayButton();
            }
        });
    });
});
