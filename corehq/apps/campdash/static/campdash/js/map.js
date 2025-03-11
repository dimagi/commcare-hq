/* Map Component for Campaign Dashboard */

// Global variable to store the map instance
let campaignMap = null;

// Initialize a map on a container element
function initMap(containerId, mapData) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Map container with ID ${containerId} not found`);
        return;
    }
    
    // Check if Leaflet is available
    if (typeof L === 'undefined') {
        // Load Leaflet dynamically if not available
        loadLeaflet().then(() => {
            createMap(container, mapData);
        });
    } else {
        createMap(container, mapData);
    }
}

// Load Leaflet library dynamically
function loadLeaflet() {
    return new Promise((resolve, reject) => {
        // Load CSS
        const cssLink = document.createElement('link');
        cssLink.rel = 'stylesheet';
        cssLink.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        document.head.appendChild(cssLink);
        
        // Load JavaScript
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Create the map with Leaflet
function createMap(container, mapData) {
    // If map already exists, remove it
    if (campaignMap) {
        campaignMap.remove();
        campaignMap = null;
    }
    
    // Extract map configuration
    const center = mapData.center || [0, 0];
    const zoom = mapData.zoom || 2;
    const markers = mapData.markers || [];
    
    // Create map
    campaignMap = L.map(container).setView(center, zoom);
    
    // Add tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(campaignMap);
    
    // Add markers based on map type
    if (mapData.type === 'markers') {
        addMarkers(campaignMap, markers);
    } else if (mapData.type === 'heatmap') {
        addHeatmap(campaignMap, markers);
    } else if (mapData.type === 'choropleth') {
        addChoropleth(campaignMap, mapData);
    }
    
    // Refresh map size after rendering
    setTimeout(() => {
        campaignMap.invalidateSize();
    }, 100);
}

// Add markers to the map
function addMarkers(map, markers) {
    if (!markers || !markers.length) return;
    
    // Create a marker cluster group if available
    const markerGroup = L.markerClusterGroup ? L.markerClusterGroup() : L.layerGroup();
    
    // Add markers
    markers.forEach(markerData => {
        if (!markerData.lat || !markerData.lng) return;
        
        const marker = L.marker([markerData.lat, markerData.lng]);
        
        // Add popup with label and value if available
        if (markerData.label || markerData.value) {
            const popupContent = `
                <div class="map-popup">
                    <h5>${markerData.label || 'Location'}</h5>
                    ${markerData.value ? `<p>Value: ${markerData.value}</p>` : ''}
                </div>
            `;
            marker.bindPopup(popupContent);
        }
        
        markerGroup.addLayer(marker);
    });
    
    map.addLayer(markerGroup);
    
    // Fit bounds to markers if there are any
    if (markers.length > 0) {
        const bounds = L.latLngBounds(markers.map(m => [m.lat, m.lng]));
        map.fitBounds(bounds);
    }
}

// Add heatmap to the map (requires Leaflet.heat plugin)
function addHeatmap(map, points) {
    if (!points || !points.length) return;
    
    // Check if heatmap plugin is available
    if (typeof L.heatLayer === 'undefined') {
        console.error('Leaflet.heat plugin is required for heatmaps');
        return;
    }
    
    // Format points for heatmap
    const heatPoints = points.map(point => {
        return [
            point.lat,
            point.lng,
            point.value || 1 // Intensity
        ];
    });
    
    // Create and add heatmap layer
    L.heatLayer(heatPoints, {
        radius: 25,
        blur: 15,
        maxZoom: 17
    }).addTo(map);
}

// Add choropleth to the map (requires GeoJSON data)
function addChoropleth(map, mapData) {
    if (!mapData.geoJson) {
        console.error('GeoJSON data is required for choropleth maps');
        return;
    }
    
    // Style function for choropleth
    function style(feature) {
        const value = feature.properties.value || 0;
        const min = mapData.min || 0;
        const max = mapData.max || 100;
        
        return {
            fillColor: getColorForValue(value, min, max),
            weight: 2,
            opacity: 1,
            color: 'white',
            dashArray: '3',
            fillOpacity: 0.7
        };
    }
    
    // Add GeoJSON layer
    L.geoJSON(mapData.geoJson, {
        style: style,
        onEachFeature: function(feature, layer) {
            // Add popup with region name and value
            if (feature.properties && feature.properties.name) {
                const value = feature.properties.value || 'N/A';
                layer.bindPopup(`
                    <div class="map-popup">
                        <h5>${feature.properties.name}</h5>
                        <p>Value: ${value}</p>
                    </div>
                `);
            }
        }
    }).addTo(map);
} 