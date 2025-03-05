/* Report Component for Campaign Dashboard */

// Initialize report functionality
document.addEventListener('DOMContentLoaded', function() {
    setupReportSorting();
    setupReportFiltering();
});

// Set up sorting functionality for report tables
function setupReportSorting() {
    document.body.addEventListener('click', function(event) {
        // Check if the clicked element is a table header
        if (event.target.tagName === 'TH') {
            const table = event.target.closest('table');
            if (!table) return;
            
            const headerIndex = Array.from(event.target.parentNode.children).indexOf(event.target);
            sortTable(table, headerIndex);
        }
    });
}

// Sort a table by a specific column
function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    // Get current sort direction
    const currentDirection = table.getAttribute('data-sort-direction') || 'asc';
    const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
    
    // Update sort direction attribute
    table.setAttribute('data-sort-direction', newDirection);
    table.setAttribute('data-sort-column', columnIndex);
    
    // Sort the rows
    rows.sort((rowA, rowB) => {
        const cellA = rowA.querySelectorAll('td')[columnIndex].textContent.trim();
        const cellB = rowB.querySelectorAll('td')[columnIndex].textContent.trim();
        
        // Check if the values are numbers
        const numA = parseFloat(cellA);
        const numB = parseFloat(cellB);
        
        if (!isNaN(numA) && !isNaN(numB)) {
            // Sort numerically
            return newDirection === 'asc' ? numA - numB : numB - numA;
        } else {
            // Sort alphabetically
            return newDirection === 'asc' 
                ? cellA.localeCompare(cellB) 
                : cellB.localeCompare(cellA);
        }
    });
    
    // Remove existing rows
    rows.forEach(row => tbody.removeChild(row));
    
    // Add sorted rows
    rows.forEach(row => tbody.appendChild(row));
    
    // Update header indicators
    updateSortIndicators(table, columnIndex, newDirection);
}

// Update sort indicators in table headers
function updateSortIndicators(table, columnIndex, direction) {
    // Remove all existing indicators
    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('sorting-asc', 'sorting-desc');
    });
    
    // Add indicator to the sorted column
    const sortedHeader = table.querySelectorAll('th')[columnIndex];
    sortedHeader.classList.add(direction === 'asc' ? 'sorting-asc' : 'sorting-desc');
}

// Set up filtering functionality for reports
function setupReportFiltering() {
    // This will be implemented when filtering UI is added
    console.log('Report filtering ready to be implemented');
}

// Export report data to CSV
function exportReportToCSV(reportData) {
    if (!reportData || !reportData.headers || !reportData.rows) {
        console.error('Invalid report data for export');
        return;
    }
    
    // Create CSV content
    let csvContent = reportData.headers.join(',') + '\n';
    
    reportData.rows.forEach(row => {
        csvContent += row.join(',') + '\n';
    });
    
    // Create download link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    
    link.setAttribute('href', url);
    link.setAttribute('download', 'campaign_report.csv');
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
} 