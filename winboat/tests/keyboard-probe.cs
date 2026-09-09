using System;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

public class KeyboardProbe : Form {
    [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    readonly TextBox editor = new TextBox();
    readonly Timer timer = new Timer();
    readonly string output;
    public KeyboardProbe(string name) {
        foreach (char c in name)
            if (!Char.IsLetterOrDigit(c) && c != '-') throw new ArgumentException("Invalid case name");
        output = "C:\\WBFreeRDP\\" + name + ".json";
        Text = "WBFreeRDP keyboard probe";
        ClientSize = new Size(700, 250);
        StartPosition = FormStartPosition.Manual;
        Location = new Point(100, 100);
        editor.Multiline = true;
        editor.Dock = DockStyle.Fill;
        editor.Font = new Font(FontFamily.GenericMonospace, 16);
        Controls.Add(editor);
        timer.Interval = 200;
        timer.Tick += delegate { Snapshot(); };
        timer.Start();
        Shown += delegate { Activate(); editor.Focus(); Snapshot(); };
        FormClosed += delegate { timer.Stop(); timer.Dispose(); };
    }
    void Snapshot() {
        long layout = GetKeyboardLayout(0).ToInt64();
        Text = "WBFreeRDP keyboard probe " + layout.ToString("x");
        string units = String.Join(",", Array.ConvertAll(editor.Text.ToCharArray(),
            delegate(char c) { return ((int)c).ToString(); }));
        string data = "{\"layout\":\"" + layout.ToString("x") + "\",\"textUtf16\":[" + units + "],\"editorFocused\":" + (editor.Focused ? "true" : "false") + ",\"foreground\":" + (GetForegroundWindow() == Handle ? "true" : "false") + "}";
        string temporary = output + ".tmp";
        try {
            File.WriteAllText(temporary, data, new UTF8Encoding(false));
            if (File.Exists(output)) File.Replace(temporary, output, null);
            else File.Move(temporary, output);
        } catch (IOException) { }
    }
    [STAThread] public static void Main(string[] args) {
        Application.EnableVisualStyles();
        Application.Run(new KeyboardProbe(args.Length > 0 ? args[0] : "keyboard-result"));
    }
}
