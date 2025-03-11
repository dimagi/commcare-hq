/* Campaign Dashboard Main JavaScript */

// Initialize the dashboard when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Campaign Dashboard initialized');
    
    // Set up HTMX events
    setupHtmxEvents();
});

// Set up HTMX events
function setupHtmxEvents() {
    // After any HTMX request completes successfully
    document.body.addEventListener('htmx:afterSwap', function(event) {
        const targetId = event.detail.target.id;
        
        // Reinitialize components based on which container was updated
        if (targetId === 'gauges-container') {
            reinitializeGauges();
        } else if (targetId === 'map-container') {
            reinitializeMap();
        }
    });
}

// Reinitialize gauges after HTMX updates
function reinitializeGauges() {
    const gauges = initialPageData.get('gauges');
    if (gauges) {
        gauges.forEach((gauge, index) => {
            initGauge('gauge-' + index, gauge);
        });
    }
}

// Reinitialize map after HTMX updates
function reinitializeMap() {
    const mapData = initialPageData.get('map_data');
    if (mapData) {
        initMap('campaign-map', mapData);
    }
}

// Utility function to format numbers
function formatNumber(number) {
    return new Intl.NumberFormat().format(number);
}

// Utility function to format percentages
function formatPercentage(value) {
    return value.toFixed(1) + '%';
}

// Utility function to get a color based on a value (for gauges and maps)
function getColorForValue(value, min, max) {
    // Calculate percentage of value between min and max
    const percentage = (value - min) / (max - min);
    
    // Color gradient from red to yellow to green
    if (percentage < 0.5) {
        // Red to yellow (0% to 50%)
        const r = 255;
        const g = Math.round(255 * (percentage * 2));
        const b = 0;
        return `rgb(${r}, ${g}, ${b})`;
    } else {
        // Yellow to green (50% to 100%)
        const r = Math.round(255 * (1 - (percentage - 0.5) * 2));
        const g = 255;
        const b = 0;
        return `rgb(${r}, ${g}, ${b})`;
    }
} 