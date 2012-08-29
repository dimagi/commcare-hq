from django.utils.html import escape

def wrapper(error):
    
    def truncate(message, length=100, append="..."):
        return "%s%s" % (message[:length], append) if len(message) > length else message
     
    domain = error.domain if hasattr(error, "domain") else ""
    return [error.get_id,
            error.archived, 
            error.date.strftime('%Y-%m-%d %H:%M:%S') if error.date else "", 
            escape(error.type), 
            truncate(error.message),
            domain,
            error.user,
            error.url,
            "archive",
            "email"]