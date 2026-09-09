using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

// An independently numbered 100 Hz GDI workload. The black/white marker survives
// lossy AVC; measuring unique markers avoids confusing repaints with new frames.
public class FrameProbe : Form {
    [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint period);
    [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint period);
    int frame;
    bool motion;
    bool gradient;
    Bitmap gradientImage;
    int[] gradientPixels;
    public FrameProbe(bool animated, bool smooth) {
        motion = animated;
        gradient = smooth;
        Text = "WBFreeRDP frame probe";
        ClientSize = gradient ? new Size(1280, 720) : new Size(960, 540);
        StartPosition = FormStartPosition.Manual;
        Location = new Point(160, 120);
        DoubleBuffered = true;
        if (gradient) {
            gradientImage = new Bitmap(1280, 720, PixelFormat.Format32bppRgb);
            gradientPixels = new int[1280 * 720];
        }
    }
    protected override void OnPaint(PaintEventArgs e) {
        if (gradient) {
            for (int y = 0; y < 720; y++)
                for (int x = 0; x < 1280; x++)
                    gradientPixels[y * 1280 + x] = unchecked((int)0xff000000)
                        | (((x + frame * 5) & 255) << 16)
                        | (((y + frame * 3) & 255) << 8)
                        | (((x + y) / 3 + frame * 7) & 255);
            BitmapData bits = gradientImage.LockBits(new Rectangle(0, 0, 1280, 720),
                ImageLockMode.WriteOnly, PixelFormat.Format32bppRgb);
            try { Marshal.Copy(gradientPixels, 0, bits.Scan0, gradientPixels.Length); }
            finally { gradientImage.UnlockBits(bits); }
            e.Graphics.DrawImageUnscaled(gradientImage, 0, 0);
        } else if (motion) {
            for (int y = 0; y < 540; y += 30)
                for (int x = 0; x < 960; x += 30)
                    using (SolidBrush brush = new SolidBrush(Color.FromArgb(
                        (x + frame * 5) & 255, (y + frame * 3) & 255,
                        ((x + y) / 3 + frame * 7) & 255)))
                        e.Graphics.FillRectangle(brush, x, y, 30, 30);
        } else e.Graphics.Clear(Color.FromArgb(32, 48, 64));
        e.Graphics.FillRectangle(Brushes.Magenta, 0, 0, 20, 20);
        for (int bit = 0; bit < 16; bit++) {
            e.Graphics.FillRectangle(((frame >> bit) & 1) != 0 ? Brushes.White : Brushes.Black,
                                     20 + bit * 20, 0, 20, 20);
            e.Graphics.FillRectangle(((frame >> bit) & 1) != 0 ? Brushes.Black : Brushes.White,
                                     20 + bit * 20, 20, 20, 20);
        }
    }
    protected override void OnFormClosed(FormClosedEventArgs e) {
        if (gradientImage != null) gradientImage.Dispose();
        base.OnFormClosed(e);
    }
    [STAThread] public static void Main(string[] args) {
        Application.EnableVisualStyles();
        using (FrameProbe probe = new FrameProbe(args.Length == 0 || args[0] != "simple",
                args.Length > 0 && args[0] == "gradient")) {
            probe.Show();
            timeBeginPeriod(1);
            Stopwatch clock = Stopwatch.StartNew();
            long next = 0;
            try {
                while (!probe.IsDisposed && clock.ElapsedMilliseconds < 90000) {
                    Application.DoEvents();
                    if (clock.ElapsedMilliseconds >= next) {
                        probe.frame++;
                        probe.Invalidate();
                        probe.Update();
                        next = clock.ElapsedMilliseconds + 10;
                    }
                    Thread.Sleep(1);
                }
            } finally { timeEndPeriod(1); }
        }
    }
}
