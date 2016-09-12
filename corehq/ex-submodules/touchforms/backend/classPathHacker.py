import java.lang.reflect.Method 
import java.lang.ClassLoader as javaClassLoader 
from java.lang import Object as javaObject 
from java.io import File as javaFile 
from java.net import URL as javaURL 
from java.net import URLClassLoader 
import jarray 

class classPathHacker(object):
    """Original Author: SG Langer Jan 2007, conversion from Java to Jython 
    Updated version (supports Jython 2.5.2) >From http://glasblog.1durch0.de/?p=846 
    
    Purpose: Allow runtime additions of new Class/jars either from 
    local files or URL

    Will Pride note: see http://stackoverflow.com/questions/11218358/jython-connect-to-mysql-driver-not-found-error
    and http://www.jython.org/jythonbook/en/1.0/appendixB.html#using-the-classpath-steve-langer

    TL;DR: we need to add the postgres JDBC drivers at runtime which Jython atm cannot do

    """ 
        
    def addFile(self, s): 
        """Purpose: If adding a file/jar call this first 
        with s = path_to_jar""" 
        # make a URL out of 's' 
        f = javaFile(s) 
        u = f.toURL() 
        a = self.addURL(u) 
        return a 
      
    def addURL(self, u): 
         """Purpose: Call this with u= URL for 
         the new Class/jar to be loaded""" 
         sysloader = javaClassLoader.getSystemClassLoader() 
         sysclass = URLClassLoader 
         method = sysclass.getDeclaredMethod("addURL", [javaURL]) 
         a = method.setAccessible(1) 
         jar_a = jarray.array([u], javaObject) 
         b = method.invoke(sysloader, [u]) 
         return u 