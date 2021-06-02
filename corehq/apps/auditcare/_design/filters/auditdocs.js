/*
 * Filter that only returns xforms.  Used by the change listener.  
 */
function(doc, req)
{   
    return (doc["base_type"] == "AuditEvent");
}

