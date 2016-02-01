jQuery(document).ready(function($) {
    // courtesy of http://colorbrewer2.org/
    var COUNTRY_COLORS = ['#fef0d9','#fdcc8a','#fc8d59','#e34a33','#b30000'];

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

        // { countryName : { projectName : { propertyName: propertyValue } } }
        var projectsByCountryThenName = {};
        var maxNumProjects = 0;
        
        that.refreshProjectData = function (filter, callback) {
            $.ajax({
                url: '/hq/admin/json/project_map/' + window.location.search,
                dataType: 'json',
            }).done(function (data) {
                var tempProjects = {};
                // data.aaData seems to hold the information. not sure though if this is the best way of getting the data.
                data.aaData.forEach(function (project) {
                    var countryNames = project[5];
                    if (!Array.isArray(countryNames) || countryNames.length < 1) {
                        // todo: find a way to display projects with no listed deployment country. ignoring for now.
                    } else {
                        // this will use only the first listed country
                        // todo: figure out desired handling of multiple deployment countries
                        var countryName = countryNames[0].toLowerCase();
                        if (!tempProjects[countryName]) {
                            tempProjects[countryName] = {};
                        }
                        tempProjects[countryName][project[0]] = {
                            'Name': project[0],
                            'Link': project[1],
                            'Date Created': project[2].substring(0,10),
                            'Organization': project[3],
                            'Deployment Date': project[4].substring(0,10),
                            'Deployment Countries': countryNames.join(', '),
                            '# Forms Submitted': project[7],
                            '# Active Mobile Workers': project[6],
                            'Notes': project[8],
                            'Sector': project[9],
                            'Sub-Sector': project[10]
                        };
                    }
                });

                projectsByCountryThenName = tempProjects;

                maxNumProjects = Object.keys(projectsByCountryThenName).reduce(function(prev, countryName) {
                    return Math.max(prev, Object.keys(projectsByCountryThenName[countryName]).length);
                }, 0);

                colorAll();

                callback();
            });
        };

        that.getNumProjects = function (countryName) {
            countryName = countryName.toLowerCase();
            return Object.keys(projectsByCountryThenName[countryName] || {}).length;
        };

        that.getMaxNumProjects = function () {
            return maxNumProjects;
        };


        var SelectionModel = function () {
            var self = this;
            self.selectedCountry = ko.observable('country name');
            self.selectedProject = ko.observable('project name');

            // for showing a country's projects table
            self.tableProperties = ['Name', 'Sector', 'Organization', 'Deployment Date'];
            self.selectedCountryProjectNames = ko.computed(function() {
                return Object.keys(projectsByCountryThenName[this.selectedCountry().toLowerCase()] || {});
            }, this);
            self.getProjectProperty = function(projectName, propertyName) {
                return ((projectsByCountryThenName[this.selectedCountry().toLowerCase()] || {})[projectName] || {})[propertyName] || '';
            };

            // for showing info on a single project
            self.projectPropertiesLeft = ['Sector', 'Sub-Sector', 'Organization', 'Deployment Countries', 'Deployment Date',
                                          '# Active Mobile Workers', '# Forms Submitted'];
            self.projectPropertiesRight = ['Notes'];
            self.getSelectedProjectProperty = function(propertyName) {
                return self.getProjectProperty(self.selectedProject(), propertyName);
            };
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

        that.showProjectInfo = function(countryName, projectIdentifier) {
            var modalContent = $('.modal-content');
            modalContent.removeClass('show-table');
            modalContent.addClass('show-project-info');

            window.location.hash ='#' + countryName + '#' + projectIdentifier;
        };

        Object.freeze(that);
        return that;
    }();

    $(document).on('click', '.project-row', function(evt) {
        var projectName = $(this).attr('data-project-name');
        selectionModel.selectedProject(projectName);
        modalController.showProjectInfo(selectionModel.selectedCountry(), projectName);
    });

    $(document).on('click', '.back', function(evt) {
        modalController.showProjectsTable(selectionModel.selectedCountry());
    });

    $('#modal').on('hidden.bs.modal', function (e) {
         window.location.hash = '';
    });

    var countriesGeo;
    // A lot of the styling work here is modeled after http://leafletjs.com/examples/choropleth.html
    var map = L.map('map').setView([0, 0], 3);
    var mapId = 'mapbox.dark';
    // copied from dimagisphere
    // todo: move to config somewhere, maybe localSettings.py?
    var accessToken = 'pk.eyJ1IjoiY3p1ZSIsImEiOiJjaWgwa3U5OXIwMGk3a3JrcjF4cjYwdGd2In0.8Tys94ISZlY-h5Y4W160RA';
    L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token={accessToken}', {
        maxZoom: 10,
        id: mapId,
        accessToken: accessToken
    }).addTo(map);

    function getColor(featureId) {
        var count = dataController.getNumProjects(featureId);
        if (!count) {
            return COUNTRY_COLORS[0];
        }
        var pct = count / dataController.getMaxNumProjects();
        var index = Math.min(Math.floor(pct * COUNTRY_COLORS.length), COUNTRY_COLORS.length - 1);

        return COUNTRY_COLORS[index];
    }

    function getOpacity(featureId) {
        if (dataController.getNumProjects(featureId)) {
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
            fillOpacity: getOpacity(feature.properties.name)
        };
    }

    // highlights
    function highlightFeature(e) {
        var layer = e.target;
        layer.setStyle({
            weight: 4,
            color: '#002c5f',
            dashArray: ''
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
            click: function(e) {
                selectionModel.selectedCountry(feature.properties.name);
                modalController.showProjectsTable(selectionModel.selectedCountry());

                // launch the modal
                $('#modal').modal();
            }
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
            var projectCount = dataController.getNumProjects(countryName);
            var message = projectCount ? projectCount + ' projects' : 'no projects';
            return '<b>' + countryName + '</b>: ' + message;
        }
        this._div.innerHTML = (props ? _getInfoContent(props.name) : 'Hover over a country');
    };
    info.addTo(map);

    // add a legend
    var legend = L.control({position: 'bottomleft'});

    legend.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info legend');

        // get the upper bounds for each bucket
        var countValues = COUNTRY_COLORS.map(function(e, i) {
            // tested this extensively
            var bound = dataController.getMaxNumProjects() * (i+1) / COUNTRY_COLORS.length;
            return Math.max(0, (i < COUNTRY_COLORS.length - 1 && Math.floor(bound) === bound) ? bound - 1 : Math.floor(bound));
        });

        // only include legend items that are actually used right now
        // when there is a low number of max projects (for example, under strict filters), they may not all be included
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

        div.innerHTML += '<i style="background:' + 'black' + '"></i> ' + '0' + '<br>'; 

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

    legend.addTo(map);

    // copied from dimagisphere
    // todo: should probably be getting this from somewhere else and possibly not on every page load.
    $.getJSON('https://raw.githubusercontent.com/dimagi/world.geo.json/master/countries.geo.json', function (data) {
        countriesGeo = L.geoJson(data, {style: style, onEachFeature: onEachFeature}).addTo(map);
        dataController.refreshProjectData({}, function() {
            // if url contains reference to a project and/or a country, load that project/country
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
});
