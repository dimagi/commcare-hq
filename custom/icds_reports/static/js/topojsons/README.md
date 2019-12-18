# State of Topojson files as of Decemer 2019

| --- File Name --- | --- Description --- | --- Used by --- | Format |
| states_v2.topojson.js | Raw state shapes for the entire country | Web dashboard and also as master file | JavaScript | 
| states_v3_small.topojson.js | Optimized state shapes for the entire country | Mobile dashboard and feature flag for new maps | topojson |
| districts_v2.topojson.js | Raw district shapes for the entire country | Web dashboard and also as master file | JavaScript | 
| districts_v3_small.topojson | Optimized district shapes for the entire country | Mobile dashboard and feature flag for new maps | topojson |
| blocks_v3.topojson.js | Raw block shapes for the entire country | Web dashboard and also as master file | JavaScript | 
| blocks/*.topojson | Raw block shapes broken down by state | Mobile dashboard and feature flag for new maps | topojson |
| district_topojson_data.json | Metadata for state / district mapping | Helper for block-level shape files used by mobile dashboard and feature flag for new maps | json |
