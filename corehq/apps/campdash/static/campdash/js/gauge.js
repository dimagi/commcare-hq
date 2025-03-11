/* Gauge Component for Campaign Dashboard */

// Initialize a gauge on a canvas element
function initGauge(canvasId, gaugeData) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.error(`Canvas element with ID ${canvasId} not found`);
        return;
    }
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear the canvas
    ctx.clearRect(0, 0, width, height);
    
    // Extract gauge data
    const value = gaugeData.value;
    const min = gaugeData.min;
    const max = gaugeData.max;
    const type = gaugeData.type;
    
    // Calculate percentage for gauge position
    const percentage = (value - min) / (max - min);
    
    // Draw the gauge
    drawGauge(ctx, width, height, percentage, value, min, max, type);
}

// Draw a gauge on a canvas context
function drawGauge(ctx, width, height, percentage, value, min, max, type) {
    // Configuration
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 2 * 0.8;
    
    // Angles (in radians)
    const startAngle = Math.PI * 0.8; // 144 degrees
    const endAngle = Math.PI * 2.2;   // 396 degrees
    const angleRange = endAngle - startAngle;
    
    // Calculate the current angle based on percentage
    const currentAngle = startAngle + (percentage * angleRange);
    
    // Get color based on percentage
    const color = getColorForValue(value, min, max);
    
    // Draw background arc (gray)
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, startAngle, endAngle);
    ctx.lineWidth = radius * 0.2;
    ctx.strokeStyle = '#e0e0e0';
    ctx.stroke();
    
    // Draw value arc (colored)
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, startAngle, currentAngle);
    ctx.lineWidth = radius * 0.2;
    ctx.strokeStyle = color;
    ctx.stroke();
    
    // Draw center circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * 0.1, 0, Math.PI * 2);
    ctx.fillStyle = '#555';
    ctx.fill();
    
    // Draw tick marks
    drawTickMarks(ctx, centerX, centerY, radius, startAngle, endAngle);
    
    // Draw needle
    drawNeedle(ctx, centerX, centerY, radius, currentAngle);
}

// Draw tick marks around the gauge
function drawTickMarks(ctx, centerX, centerY, radius, startAngle, endAngle) {
    const tickCount = 10;
    const angleStep = (endAngle - startAngle) / tickCount;
    
    for (let i = 0; i <= tickCount; i++) {
        const angle = startAngle + (i * angleStep);
        
        // Calculate tick start and end points
        const outerRadius = radius * 1.05;
        const innerRadius = radius * 0.95;
        
        const startX = centerX + Math.cos(angle) * innerRadius;
        const startY = centerY + Math.sin(angle) * innerRadius;
        const endX = centerX + Math.cos(angle) * outerRadius;
        const endY = centerY + Math.sin(angle) * outerRadius;
        
        // Draw tick
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#888';
        ctx.stroke();
    }
}

// Draw the needle pointing to the current value
function drawNeedle(ctx, centerX, centerY, radius, angle) {
    // Needle length and width
    const needleLength = radius * 0.8;
    const needleWidth = radius * 0.05;
    
    // Calculate needle endpoint
    const endX = centerX + Math.cos(angle) * needleLength;
    const endY = centerY + Math.sin(angle) * needleLength;
    
    // Calculate points for needle shape
    const leftX = centerX + Math.cos(angle + Math.PI/2) * needleWidth;
    const leftY = centerY + Math.sin(angle + Math.PI/2) * needleWidth;
    const rightX = centerX + Math.cos(angle - Math.PI/2) * needleWidth;
    const rightY = centerY + Math.sin(angle - Math.PI/2) * needleWidth;
    
    // Draw needle
    ctx.beginPath();
    ctx.moveTo(leftX, leftY);
    ctx.lineTo(endX, endY);
    ctx.lineTo(rightX, rightY);
    ctx.closePath();
    ctx.fillStyle = '#333';
    ctx.fill();
    
    // Draw center cap
    ctx.beginPath();
    ctx.arc(centerX, centerY, needleWidth * 1.5, 0, Math.PI * 2);
    ctx.fillStyle = '#555';
    ctx.fill();
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.stroke();
} 