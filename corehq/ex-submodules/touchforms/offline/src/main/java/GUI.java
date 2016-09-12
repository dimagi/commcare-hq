import java.awt.*;
import java.awt.event.*;
import javax.swing.*;

public class GUI {
    final String CMD_CLOSE = "Close";
    final String NAME = "Offline Cloudcare";

    boolean loaded;
    
    MenuItem status;
    TrayIcon icon;

    int numSessions;

    public void load() {
        boolean usingSystray = false;
        if (SystemTray.isSupported()) {
            SystemTray tray = SystemTray.getSystemTray();
            Image image = Toolkit.getDefaultToolkit().getImage(GUI.class.getResource("systray.png"));
            ActionListener listener = new ActionListener() {
                    public void actionPerformed(ActionEvent e) {
                        String cmd = e.getActionCommand();
                        if (cmd == null) {
                            // systray icon was double-clicked
                            // TODO do something cool
                        } else if (cmd == CMD_CLOSE) {
                            // TODO warn if active sessions
                            System.exit(0);
                        }
                    }
                };

            // systray doesn't support swing menus... come on!!
            PopupMenu popup = new PopupMenu();
            MenuItem close = new MenuItem(CMD_CLOSE);
            close.addActionListener(listener);

            this.status = new MenuItem("Starting up...");
                
            popup.add(status);
            popup.addSeparator();
            popup.add(close);

            this.icon = new TrayIcon(image, NAME, popup);
            this.icon.addActionListener(listener);
            this.icon.setImageAutoSize(true);

            try {
                tray.add(this.icon);
                usingSystray = true;
            } catch (AWTException e) { }
        }

        if (!usingSystray) {
            // TODO fallback to a normal GUI window
        }

        this.loaded = true;
    }

    public void setNumSessions(int numSessions) {
        this.numSessions = numSessions;

        if (!this.loaded) {
            return;
        }

        String sess = (numSessions > 0 ? numSessions : "no") + " active " + (numSessions == 1 ? "session" : "sessions");
        this.status.setLabel("Running... " + sess);
        this.icon.setToolTip(NAME + (numSessions > 0 ? ": " + sess : ""));
    }

}