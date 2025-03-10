# Campaign Dashboard

A dashboard for tracking the progress of campaigns with customizable gauges, reports, and maps.

## Features

- **Gauges**: Speedometer-style gauges to display key metrics
- **Reports**: Tabular data with sorting and filtering capabilities
- **Maps**: Geographic visualization of campaign data

## Technical Details

- Uses HTMX for dynamic content updates without full page reloads
- Uses Alpine.js for reactive UI components
- Gauges are rendered using HTML5 Canvas
- Maps are powered by Leaflet.js

## Development

### Models

The app includes the following models:

- `CampaignDashboard`: Main configuration for a dashboard
- `DashboardGauge`: Configuration for gauge components
- `DashboardReport`: Configuration for report components
- `DashboardMap`: Configuration for map components

### Frontend Components

- Gauges: Speedometer-style gauges rendered with Canvas
- Reports: Sortable tables with HTMX-powered refresh
- Maps: Interactive maps with markers, heatmaps, or choropleth visualizations

### Future Enhancements

- User-customizable dashboard layouts
- Additional visualization types
- Data export capabilities
- Integration with other CommCare HQ data sources 