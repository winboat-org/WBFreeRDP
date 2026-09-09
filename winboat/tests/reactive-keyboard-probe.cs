using System;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

public class ReactiveKeyboardProbe : Form {
    [DllImport("user32.dll")] static extern short GetKeyState(int key);
    readonly System.Collections.Generic.List<int> downs = new System.Collections.Generic.List<int>();
    readonly System.Collections.Generic.List<int> ups = new System.Collections.Generic.List<int>();
    [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    readonly System.Collections.Generic.List<string> trace = new System.Collections.Generic.List<string>();
    readonly TextBox editor = new TextBox();
    readonly Timer timer = new Timer();
    readonly string output;
    public ReactiveKeyboardProbe(string name) {
        foreach (char c in name)
            if (!Char.IsLetterOrDigit(c) && c != '-') throw new ArgumentException("Invalid case name");
        output = "C:\\WBFreeRDP\\" + name + ".json";
        Text = "WBFreeRDP reactive keyboard probe";
        ClientSize = new Size(700, 250);
        StartPosition = FormStartPosition.Manual;
        Location = new Point(100, 100);
        editor.Multiline = true;
        editor.Dock = DockStyle.Fill;
        editor.Font = new Font(FontFamily.GenericMonospace, 16);
        Controls.Add(editor);
        editor.KeyDown += delegate(object sender, KeyEventArgs e) { downs.Add((int)e.KeyCode); Record("down", (int)e.KeyCode); Snapshot(); };
        editor.KeyUp += delegate(object sender, KeyEventArgs e) { ups.Add((int)e.KeyCode); Record("up", (int)e.KeyCode); Snapshot(); };
        timer.Interval = 200;
        timer.Tick += delegate { Snapshot(); };
        timer.Start();
        Shown += delegate { Activate(); editor.Focus(); Snapshot(); };
        FormClosed += delegate { timer.Stop(); timer.Dispose(); };
    }
    void Record(string kind, int key) {
        if (trace == null || trace.Count >= 512) return;
        trace.Add("{\"kind\":\"" + kind + "\",\"key\":" + key
            + ",\"ticks\":" + Environment.TickCount
            + ",\"utc\":\"" + DateTime.UtcNow.ToString("O")
            + "\",\"layout\":\"" + GetKeyboardLayout(0).ToInt64().ToString("x") + "\"}");
    }
    protected override void WndProc(ref Message message) {
        if (message.Msg == 0x50) Record("layout-request", 0);
        base.WndProc(ref message);
        if (message.Msg == 0x51) Record("layout-changed", 0);
    }
    void Snapshot() {
        long layout = GetKeyboardLayout(0).ToInt64();
        Text = "WBFreeRDP reactive keyboard probe " + layout.ToString("x");
        string units = String.Join(",", Array.ConvertAll(editor.Text.ToCharArray(),
            delegate(char c) { return ((int)c).ToString(); }));
        string data = "{\"layout\":\"" + layout.ToString("x") + "\",\"textUtf16\":[" + units + "],\"editorFocused\":" + (editor.Focused ? "true" : "false") + ",\"foreground\":" + (GetForegroundWindow() == Handle ? "true" : "false") + "}";
        data = data.Substring(0, data.Length - 1) + ",\"aDown\":" + ((GetKeyState(65) & 0x8000) != 0 ? "true" : "false")
            + ",\"yDown\":" + ((GetKeyState(89) & 0x8000) != 0 ? "true" : "false")
            + ",\"zDown\":" + ((GetKeyState(90) & 0x8000) != 0 ? "true" : "false")
            + ",\"shiftDown\":" + ((GetKeyState(16) & 0x8000) != 0 ? "true" : "false")
            + ",\"downs\":[" + String.Join(",", downs.ToArray()) + "],\"ups\":[" + String.Join(",", ups.ToArray()) + "],\"trace\":[" + String.Join(",", trace.ToArray()) + "]}";
        string temporary = output + ".tmp";
        try {
            File.WriteAllText(temporary, data, new UTF8Encoding(false));
            if (File.Exists(output)) File.Replace(temporary, output, null);
            else File.Move(temporary, output);
        } catch (IOException) { }
    }
    [STAThread] public static void Main(string[] args) {
        Application.EnableVisualStyles();
        Application.Run(new ReactiveKeyboardProbe(args.Length > 0 ? args[0] : "keyboard-result"));
    }
}
