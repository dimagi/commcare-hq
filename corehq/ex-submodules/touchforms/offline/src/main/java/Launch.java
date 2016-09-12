import java.io.*;
import org.python.core.*;
import org.python.util.*;

public class Launch {

    public static void main (String[] args) {

        PySystemState state = new PySystemState();
        //state.argv.append(new PyString(""));

        PythonInterpreter interpreter = new PythonInterpreter(null, state);

        InputStream is = Launch.class.getResourceAsStream("Lib/__run__.py");
        interpreter.execfile(is);
        
    }

}