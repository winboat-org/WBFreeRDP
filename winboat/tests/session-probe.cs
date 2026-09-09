using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

sealed class SessionCanvas : Control {
    public uint Frame;
    readonly SolidBrush[] colors = new SolidBrush[24];
    public SessionCanvas() {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                 ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        for (int i=0; i<colors.Length; i++)
            colors[i] = new SolidBrush(Color.FromArgb((i*31)&255,(i*53)&255,(i*79)&255));
    }
    protected override void OnPaint(PaintEventArgs e) {
        for(int y=32; y<Height; y+=32)
            for(int x=0; x<Width; x+=32)
                e.Graphics.FillRectangle(colors[(x/32+y/32+(int)(Frame%24))%24],x,y,32,32);
        e.Graphics.FillRectangle(Brushes.DarkSlateGray,0,0,Width,32);
        e.Graphics.FillRectangle(Brushes.Magenta,0,0,16,16);
        for(int bit=0; bit<32; bit++) {
            bool set = ((Frame>>bit)&1)!=0;
            e.Graphics.FillRectangle(set?Brushes.White:Brushes.Black,16+bit*8,0,8,16);
            e.Graphics.FillRectangle(set?Brushes.Black:Brushes.White,16+bit*8,16,8,16);
        }
        e.Graphics.FillRectangle(Brushes.Yellow,Width-12,Height-12,12,12);
    }
    protected override void Dispose(bool disposing) {
        if(disposing) foreach(SolidBrush color in colors) color.Dispose();
        base.Dispose(disposing);
    }
}

public sealed class SessionProbe : Form {
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int Left,Top,Right,Bottom; }
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr hwnd,int attribute,out RECT value,int size);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetGuiResources(IntPtr process,uint flags);
    readonly TextBox editor = new TextBox();
    readonly Button button = new Button();
    readonly Label label = new Label();
    readonly SessionCanvas canvas = new SessionCanvas();
    readonly Timer timer = new Timer();
    readonly Stopwatch clock = Stopwatch.StartNew();
    readonly Process process = Process.GetCurrentProcess();
    readonly string output;
    readonly int lifetimeSeconds;
    long lastSnapshot;
    int clicks, resizes;
    public SessionProbe(string name,int seconds) {
        foreach(char c in name)
            if(!Char.IsLetterOrDigit(c) && c!='-') throw new ArgumentException("Invalid name");
        output="C:\\WBFreeRDP\\session-"+name+".json";
        lifetimeSeconds=seconds;
        Text="WBFreeRDP session probe "+name;
        AutoScaleMode=AutoScaleMode.None;
        ClientSize=new Size(720,480);
        MinimumSize=new Size(480,320);
        StartPosition=FormStartPosition.Manual;
        Location=new Point(100,80);
        Panel header=new Panel { Dock=DockStyle.Top,Height=96 };
        editor.SetBounds(16,12,300,28);
        editor.Font=new Font(FontFamily.GenericMonospace,12);
        button.SetBounds(340,12,140,32);
        button.Text="Count click";
        button.Click+=delegate { clicks++;editor.Focus();Snapshot(); };
        label.SetBounds(16,52,600,30);
        header.Controls.Add(editor);header.Controls.Add(button);header.Controls.Add(label);
        canvas.Dock=DockStyle.Fill;
        Controls.Add(canvas);Controls.Add(header);
        Resize+=delegate { resizes++; };
        Shown+=delegate { Activate();editor.Focus();Snapshot(); };
        timer.Interval=20;
        timer.Tick+=delegate {
            canvas.Frame++;
            canvas.Invalidate();
            if(clock.ElapsedMilliseconds-lastSnapshot>=250) {
                lastSnapshot=clock.ElapsedMilliseconds;Snapshot();
            }
            if(clock.Elapsed.TotalSeconds>=lifetimeSeconds) Close();
        };
        timer.Start();
        FormClosed+=delegate { timer.Stop();timer.Dispose();process.Dispose(); };
    }
    void Snapshot() {
        process.Refresh();
        RECT visible;
        int frameResult=DwmGetWindowAttribute(Handle,9,out visible,Marshal.SizeOf(typeof(RECT)));
        label.Text="PID "+process.Id+"   frame "+canvas.Frame+"   clicks "+clicks+"   resizes "+resizes;
        string units=String.Join(",",Array.ConvertAll(editor.Text.ToCharArray(),
            delegate(char c) { return ((int)c).ToString(); }));
        string data="{\"pid\":"+process.Id+",\"sessionId\":"+process.SessionId+
            ",\"hwnd\":\""+Handle.ToInt64().ToString("x")+"\",\"elapsedMs\":"+clock.ElapsedMilliseconds+
            ",\"frame\":"+canvas.Frame+",\"clicks\":"+clicks+",\"resizes\":"+resizes+
            ",\"outerWidth\":"+Width+",\"outerHeight\":"+Height+
            ",\"frameBoundsResult\":"+frameResult+",\"visibleWidth\":"+(visible.Right-visible.Left)+",\"visibleHeight\":"+(visible.Bottom-visible.Top)+
            ",\"clientWidth\":"+ClientSize.Width+",\"clientHeight\":"+ClientSize.Height+
            ",\"canvasWidth\":"+canvas.Width+",\"canvasHeight\":"+canvas.Height+
            ",\"gdiHandles\":"+GetGuiResources(process.Handle,0)+
            ",\"userHandles\":"+GetGuiResources(process.Handle,1)+
            ",\"privateBytes\":"+process.PrivateMemorySize64+
            ",\"editorFocused\":"+(editor.Focused?"true":"false")+
            ",\"foreground\":"+(GetForegroundWindow()==Handle?"true":"false")+
            ",\"textUtf16\":["+units+"]}";
        string temporary=output+".tmp";
        try {
            File.WriteAllText(temporary,data,new UTF8Encoding(false));
            if(File.Exists(output)) File.Replace(temporary,output,null);
            else File.Move(temporary,output);
        } catch(IOException) { }
    }
    [STAThread] public static void Main(string[] args) {
        SetProcessDPIAware();
        Application.EnableVisualStyles();
        int lifetime=args.Length>1?Int32.Parse(args[1]):3600;
        if(lifetime<10 || lifetime>7200) throw new ArgumentException("Invalid lifetime");
        Application.Run(new SessionProbe(args[0],lifetime));
    }
}
