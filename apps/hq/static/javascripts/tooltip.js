/************************************************************************************************************
    (C) www.dhtmlgoodies.com, October 2005
    
    This is a script from www.dhtmlgoodies.com. You will find this and a lot of other scripts at our website.   
    
    Terms of use:
    You are free to use this script as long as the copyright message is kept intact. However, you may not
    redistribute, sell or repost it without our permission.
    
    Thank you!
    
    Updated:    April, 6th 2006, Using iframe in IE in order to make the tooltip cover select boxes.
    
    www.dhtmlgoodies.com
    Alf Magne Kalleland
    
    ************************************************************************************************************/   
    var dhtmlgoodies_tooltip = false;
    var dhtmlgoodies_tooltipShadow = false;
    var dhtmlgoodies_shadowSize = 4;
    var dhtmlgoodies_tooltipMaxWidth = 200;
    var dhtmlgoodies_tooltipMinWidth = 100;
    var dhtmlgoodies_iframe = false;
    var tooltip_is_msie = (navigator.userAgent.indexOf('MSIE')>=0 && navigator.userAgent.indexOf('opera')==-1 && document.all)?true:false;
    function showTooltip(e,tooltipTxt)
    {
        
        var bodyWidth = Math.max(document.body.clientWidth,document.documentElement.clientWidth) - 20;
    
        if(!dhtmlgoodies_tooltip){
            dhtmlgoodies_tooltip = document.createElement('DIV');
            dhtmlgoodies_tooltip.id = 'dhtmlgoodies_tooltip';
            dhtmlgoodies_tooltipShadow = document.createElement('DIV');
            dhtmlgoodies_tooltipShadow.id = 'dhtmlgoodies_tooltipShadow';
            
            document.body.appendChild(dhtmlgoodies_tooltip);
            document.body.appendChild(dhtmlgoodies_tooltipShadow);  
            
            if(tooltip_is_msie){
                dhtmlgoodies_iframe = document.createElement('IFRAME');
                dhtmlgoodies_iframe.frameborder='5';
                dhtmlgoodies_iframe.style.backgroundColor='#FFFFFF';
                dhtmlgoodies_iframe.src = '#';  
                dhtmlgoodies_iframe.style.zIndex = 100;
                dhtmlgoodies_iframe.style.position = 'absolute';
                document.body.appendChild(dhtmlgoodies_iframe);
            }
            
        }
        
        dhtmlgoodies_tooltip.style.display='block';
        dhtmlgoodies_tooltipShadow.style.display='block';
        if(tooltip_is_msie)dhtmlgoodies_iframe.style.display='block';
        
        var st = Math.max(document.body.scrollTop,document.documentElement.scrollTop);
        if(navigator.userAgent.toLowerCase().indexOf('safari')>=0)st=0; 
        var leftPos = e.clientX + 10;
        
        dhtmlgoodies_tooltip.style.width = null;    // Reset style width if it's set 
        dhtmlgoodies_tooltip.innerHTML = tooltipTxt;
        dhtmlgoodies_tooltip.style.left = leftPos + 'px';
        dhtmlgoodies_tooltip.style.top = e.clientY + 10 + st + 'px';

        
        dhtmlgoodies_tooltipShadow.style.left =  leftPos + dhtmlgoodies_shadowSize + 'px';
        dhtmlgoodies_tooltipShadow.style.top = e.clientY + 10 + st + dhtmlgoodies_shadowSize + 'px';
        
        if(dhtmlgoodies_tooltip.offsetWidth>dhtmlgoodies_tooltipMaxWidth){  /* Exceeding max width of tooltip ? */
            dhtmlgoodies_tooltip.style.width = dhtmlgoodies_tooltipMaxWidth + 'px';
        }
        
        var tooltipWidth = dhtmlgoodies_tooltip.offsetWidth;        
        if(tooltipWidth<dhtmlgoodies_tooltipMinWidth)tooltipWidth = dhtmlgoodies_tooltipMinWidth;
        
        
        dhtmlgoodies_tooltip.style.width = tooltipWidth + 'px';
        dhtmlgoodies_tooltipShadow.style.width = dhtmlgoodies_tooltip.offsetWidth + 'px';
        dhtmlgoodies_tooltipShadow.style.height = dhtmlgoodies_tooltip.offsetHeight + 'px';     
        
        if((leftPos + tooltipWidth)>bodyWidth){
            dhtmlgoodies_tooltip.style.left = (dhtmlgoodies_tooltipShadow.style.left.replace('px','') - ((leftPos + tooltipWidth)-bodyWidth)) + 'px';
            dhtmlgoodies_tooltipShadow.style.left = (dhtmlgoodies_tooltipShadow.style.left.replace('px','') - ((leftPos + tooltipWidth)-bodyWidth) + dhtmlgoodies_shadowSize) + 'px';
        }
        
        if(tooltip_is_msie){
            dhtmlgoodies_iframe.style.left = dhtmlgoodies_tooltip.style.left;
            dhtmlgoodies_iframe.style.top = dhtmlgoodies_tooltip.style.top;
            dhtmlgoodies_iframe.style.width = dhtmlgoodies_tooltip.offsetWidth + 'px';
            dhtmlgoodies_iframe.style.height = dhtmlgoodies_tooltip.offsetHeight + 'px';
        
        }
                
    }
    
    function hideTooltip()
    {
        dhtmlgoodies_tooltip.style.display='none';
        dhtmlgoodies_tooltipShadow.style.display='none';        
        if(tooltip_is_msie)dhtmlgoodies_iframe.style.display='none';        
    }

function simple_tooltip(target_items, name){
 $(target_items).each(function(i){
        $("body").append("<div class='"+name+"' id='"+name+i+"'><p>"+$(this).attr('title')+"</p></div>");
        var my_tooltip = $("#"+name+i);
        
        $(this).removeAttr("title").mouseover(function(){
                my_tooltip.css({opacity:0.8, display:"none"}).fadeIn(100);
        }).mousemove(function(kmouse){
                my_tooltip.css({left:kmouse.pageX+15, top:kmouse.pageY+15});
        }).mouseout(function(){
                my_tooltip.fadeOut(100);                  
        });
    });
}

    
$(document).ready(function(){
     simple_tooltip("a","tooltip");
});