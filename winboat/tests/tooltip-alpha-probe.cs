using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

class TooltipAlphaProbe : Form
{
    readonly ToolTip tip = new ToolTip();
    readonly Timer timer = new Timer();
    readonly StreamWriter log;
    int step;
    Form layered;
    public TooltipAlphaProbe(string label)
    {
        Text = "WBFreeRDP tooltip alpha probe";
        StartPosition = FormStartPosition.Manual;
        Location = new Point(350, 200);
        ClientSize = new Size(700, 400);
        BackColor = Color.FromArgb(32, 64, 128);
        DoubleBuffered = true;
        log = new StreamWriter("C:/WBFreeRDP/" + label + ".jsonl");
        log.AutoFlush = true;
        tip.UseAnimation = true;
        tip.UseFading = true;
        tip.ShowAlways = true;
        tip.InitialDelay = 200;
        tip.AutoPopDelay = 1000;
        timer.Interval = 600;
        timer.Tick += Tick;
        Shown += delegate { Record("shown"); timer.Start(); };
        FormClosed += delegate { timer.Stop(); tip.Dispose(); if (layered != null) layered.Dispose(); log.Dispose(); };
    }
    void Record(string action)
    {
        log.WriteLine("{\"utc\":\"" + DateTime.UtcNow.ToString("o") + "\",\"action\":\"" + action + "\",\"step\":" + step + "}");
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        for (int y = 0; y < 400; y += 40)
            for (int x = 0; x < 700; x += 40)
                if ((x / 40 + y / 40) % 2 == 0) e.Graphics.FillRectangle(Brushes.DarkSlateBlue, x, y, 40, 40);
        e.Graphics.DrawString("Temporary tooltip / alpha test — closes automatically", Font, Brushes.White, 20, 20);
    }
    void Tick(object sender, EventArgs e)
    {
        if (step < 12)
        {
            if (step % 2 == 0) { tip.Show("Tooltip fade test: unchanged background", this, 150, 160); Record("tooltip-show"); }
            else { tip.Hide(this); Record("tooltip-hide"); }
        }
        else if (step == 12)
        {
            layered = new Form();
            layered.Text = "WBFreeRDP layered alpha probe";
            layered.FormBorderStyle = FormBorderStyle.None;
            layered.ShowInTaskbar = false;
            layered.StartPosition = FormStartPosition.Manual;
            layered.Location = PointToScreen(new Point(150, 230));
            layered.ClientSize = new Size(320, 55);
            layered.BackColor = Color.Gold;
            layered.Opacity = 0.9;
            layered.Show(this);
            Record("layered-show");
            timer.Interval = 80;
        }
        else if (step < 42)
        {
            layered.Opacity = 0.1 + 0.8 * ((step - 13) % 10) / 9.0;
            Record("layered-opacity");
        }
        else { Record("done"); Close(); return; }
        step++;
    }
    [STAThread] static int Main(string[] args)
    {
        if (args.Length != 1 || args[0].IndexOfAny(Path.GetInvalidFileNameChars()) >= 0) return 2;
        Application.EnableVisualStyles();
        Application.Run(new TooltipAlphaProbe(args[0]));
        return 0;
    }
}
