/* globals hqDefine */
hqDefine('hqadmin/js/project_map', function () {
    $(function() {
        // courtesy of http://colorbrewer2.org/
        var COUNTRY_COLORS = ['#fef0d9','#fdd49e','#fdbb84','#fc8d59','#e34a33','#b30000'];
        var PROJECT_COUNTS_THRESHOLD = [10, 20, 30, 40, 50];
        var USER_COUNTS_THRESHOLD = [10, 100, 500, 1000, 4000];
        var mapboxAccessToken = $("#map").data("token");

        var selectionModel;

        function colorAll() {
            if (countriesGeo !== undefined) {
                countriesGeo.setStyle(style);
                map.removeControl(legend);
                legend.addTo(map);
            }
        }

        var dataController = function() {
            var that = {};
            var maxNumProjects = 0;
            var maxNumUsers = 0;
            var totalNumUsers = 0;
            var totalNumProjects = 0;
            var projects_per_country = {};
            var users_per_country = {};
            var is_project_count_map = true;
    
            that.refreshProjectData = function (filter, callback) {
                $.ajax({
                    url: '/hq/admin/json/project_map/' + window.location.search,
                    dataType: 'json',
                }).done(function (data) {
    
                    projects_per_country = data.country_projs_count;
                    users_per_country = data.users_per_country;
                    totalNumProjects = data.total_num_projects;
    
                    Object.keys(projects_per_country).map(function(country) {
                        if (projects_per_country[country] > maxNumProjects) {
                            maxNumProjects = projects_per_country[country];
                        }
                    });
    
                    Object.keys(users_per_country).map(function(country) {
                        if (users_per_country[country] > maxNumUsers) {
                            maxNumUsers = users_per_country[country];
                        }
                        totalNumUsers += users_per_country[country];
                    });
    
                    colorAll();
                    callback();
                });
            };
    
            that.getCount = function (countryName) {
                countryName = countryName.toUpperCase();
                if (is_project_count_map) {
                    return projects_per_country[countryName] || 0;
                } else {
                    return users_per_country[countryName] || 0;
                }
            };
    
            that.toggleMap = function () {
                is_project_count_map = !is_project_count_map;
            };
    
            that.getUnit = function (count) {
                if (is_project_count_map) {
                    return count > 1 ? 'active projects' : 'active project';
                } else {
                    return count > 1 ? 'active users' : 'active user';
                }
            };
    
            that.getNumActiveCountries = function () {
                return Object.keys(projects_per_country).length;
            };
    
            that.getMax = function () {
                if (is_project_count_map) {
                    return maxNumProjects;
                } else {
                    return maxNumUsers;
                }
            };
    
            that.getNumProjects = function () {
                return totalNumProjects;
            };
    
            that.getNumUsers = function () {
                return totalNumUsers;
            };
    
            that.isProjectCountMap = function (){
                return is_project_count_map;
            };
    
            var SelectionModel = function () {
                var self = this;
                self.selectedCountry = ko.observable('country name');
                self.selectedProject = ko.observable('project name');
                self.internalTableProperties = ['Name', 'Organization', 'Notes', 'Sector', 'Sub-Sector', 'Active Users', 'Countries'];
                self.externalTableProperties = ['Sector', 'Sub-Sector', 'Active Users', 'Countries'];
                self.topFiveProjects = ko.observableArray();
            };
    
            selectionModel = new SelectionModel();
            $('#modal').koApplyBindings(selectionModel);
    
            Object.freeze(that);
            return that;
        }();
    
        var modalController = function(){
            var that = {};
    
            that.showProjectsTable = function(countryName) {
                var modalContent = $('.modal-content');
                modalContent.addClass('show-table');
                modalContent.removeClass('show-project-info');
    
                window.location.hash = countryName;
            };
    
            Object.freeze(that);
            return that;
        }();
    
        var countriesGeo;
        // A lot of the styling work here is modeled after http://leafletjs.com/examples/choropleth.html
        var map = L.map('map').setView([0, 0], 3);
        var mapId = 'dimagi/cirqobc2w0000g4ksj9dochrm';
    
        // copied from dimagisphere
        L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/256/{z}/{x}/{y}?access_token={accessToken}', {
            maxZoom: 6,
            minZoom: 2,
            id: mapId,
            accessToken: mapboxAccessToken,
            noWrap: true,
        }).addTo(map);
    
        var southWest = L.latLng(-85.0, -180.0),
            northEast = L.latLng(85.0, 180.0),
            bounds = L.latLngBounds(southWest, northEast);
    
        map.setMaxBounds(bounds);
        map.on('drag', function(){
            map.panInsideBounds(bounds, {animate:false});
        });
    
        function getColor(featureId) {
            var thresholdScales;
            var count = dataController.getCount(featureId);
            var isProjectCountMap = dataController.isProjectCountMap();
            if (isProjectCountMap) {
                thresholdScales = PROJECT_COUNTS_THRESHOLD;
            } else {
                thresholdScales = USER_COUNTS_THRESHOLD;
            }
            var index = getColorScaleIndex(count, thresholdScales);
            return COUNTRY_COLORS[index];
        }
    
        function getColorScaleIndex(count, scales) {
            for (var i = 0; i < scales.length; i++){
                if (count < scales[i]){
                    return i;
                }
            }
            return scales.length;
        }
    
        function getOpacity(featureId) {
            if (dataController.getCount(featureId)) {
                return 0.9;
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
    
        function formatCountryNames(countries) {
            return countries.map(function(country) {
                var formattedCountryName = country.charAt(0).toUpperCase();
                if (country.indexOf(",") > -1) {
                    formattedCountryName += country.substring(1, country.indexOf(",")).toLowerCase();
                } else {
                    formattedCountryName += country.substring(1).toLowerCase();
                }
                return formattedCountryName;
            });
        }
    
        function onEachFeature(feature, layer) {
            layer.on({
                mouseover: highlightFeature,
                mouseout: resetHighlight,
                click: function(e) {
                    if (dataController.getCount(feature.properties.name)){
                        selectionModel.selectedCountry(feature.properties.name);
                        modalController.showProjectsTable(selectionModel.selectedCountry());
                        var country = (feature.properties.name).toUpperCase();
                        selectionModel.topFiveProjects.removeAll();
                        $.ajax({
                            url: "/hq/admin/top_five_projects_by_country/?country=" + country,
                            datatype: "json",
                        }).done(function(data){
                            if (data.internal) {
                                data[country].forEach(function(project){
                                    selectionModel.topFiveProjects.push({
                                        name: project['name'],
                                        organization: project['organization_name'],
                                        description: project['internal']['notes'],
                                        sector: project['internal']['area'],
                                        sub_sector: project['internal']['sub_area'],
                                        active_users: project['cp_n_active_cc_users'],
                                        countries: formatCountryNames(project['deployment']['countries']).join(', '),
                                    });
                                });
                            } else {
                                data[country].forEach(function(project){
                                    selectionModel.topFiveProjects.push({
                                        sector: project['internal']['area'],
                                        sub_sector: project['internal']['sub_area'],
                                        active_users: project['cp_n_active_cc_users'],
                                        countries: formatCountryNames(project['deployment']['countries']).join(', '),
                                    });
                                });
                            }
    
                        });
                        $('#modal').modal();
                    }
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
                var count = dataController.getCount(countryName);
                var unit = dataController.getUnit(count);
                var message = count ? count + ' ' + unit : 'no ' + unit + 's';
                return '<b>' + countryName + '</b>: ' + message;
            }
            this._div.innerHTML = (props ? _getInfoContent(props.name) : 'Hover over a country');
        };
        info.addTo(map);
    
        // add a legend
        var legend = L.control({position: 'bottomleft'});
    
        legend.onAdd = function (map) {
            var div = L.DomUtil.create('div', 'info legend');
            var thresholds;
            div.innerHTML += '<i style="background:' + 'black' + '"></i> ' + '0' + '<br>';
            var is_project_count_map = dataController.isProjectCountMap();
            if (is_project_count_map) {
                thresholds = PROJECT_COUNTS_THRESHOLD;
            } else {
                thresholds = USER_COUNTS_THRESHOLD;
            }
            for (var i = 0; i < thresholds.length; i++) {
                div.innerHTML += '<i style="background:' + COUNTRY_COLORS[i] + '"></i> ';
                if (thresholds[i-1] !==  undefined) {
                    if (thresholds[i-1] +1 < thresholds[i]) {
                        div.innerHTML += (thresholds[i-1] + 1) + '&ndash;';
                    }
                } else if (thresholds[i] > 1) {
                    div.innerHTML += '1&ndash;';
                }
                div.innerHTML += thresholds[i] + '<br>';
            }
            div.innerHTML += '<i style="background:' + COUNTRY_COLORS[thresholds.length] + '"></i> '
                             + (thresholds[thresholds.length-1] + 1)+ '+';
    
            return div;
        };
    
        legend.addTo(map);
    
    
        var stats = L.control({position: 'bottomright'});
    
        stats.onAdd = function (map) {
            var div = L.DomUtil.create('div', 'info legend');
            div.innerHTML += '<p><b>Statistics</b></p>';
            div.innerHTML += '<p>Number of Active Countries: ' + dataController.getNumActiveCountries() +  '</p>';
            div.innerHTML += '<p>Number of Active Mobile Users: ' + dataController.getNumUsers() +  '</p>';
            div.innerHTML += '<p>Number of Active Projects: ' + dataController.getNumProjects() +  '</p>';
            div.innerHTML += '<br><p><em> Active: A project or user submitted a form in past 30 days.</em></p>';
            return div;
        };

        // copied from dimagisphere
        // todo: should probably be getting this from somewhere else and possibly not on every page load.
        $.getJSON('https://raw.githubusercontent.com/dimagi/world.geo.json/master/countries.geo.json', function (data) {
            countriesGeo = L.geoJson(data, {style: style, onEachFeature: onEachFeature}).addTo(map);
            dataController.refreshProjectData({}, function() {
    
                stats.addTo(map);
    
                var references = window.location.hash.substring(1).split('#');
                if (references.length === 2) {
                    // country, then project
                    selectionModel.selectedCountry(references[0]);
                    selectionModel.selectedProject(references[1]);
                    modalController.showProjectInfo(references[0], references[1]);
                    $('#modal').modal();
                } else if (references.length === 1 && references[0].length > 0) {
                    // just a country
                    selectionModel.selectedCountry(references[0]);
                    modalController.showProjectsTable(references[0]);
                    $('#modal').modal();
                }
            });
        });
    
        $('.btn-toggle').click(function() {
            dataController.toggleMap();
            dataController.refreshProjectData({}, function(){});
            $(this).find('.btn').toggleClass('btn-primary');
            $(this).find('.btn').toggleClass('btn-default');
        });
    });
});
