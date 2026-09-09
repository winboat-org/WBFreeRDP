// SPDX-License-Identifier: Apache-2.0
// Run as a RemoteApp. The host runner routes audio only through private null sinks.
using System;
using System.Collections.Generic;
using System.IO;
using System.Media;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

sealed class PortableIoProbe : Form {
    [StructLayout(LayoutKind.Sequential, Pack=2)] struct WaveFormat {
        public ushort FormatTag, Channels;
        public uint SamplesPerSec, AvgBytesPerSec;
        public ushort BlockAlign, BitsPerSample, Size;
    }
    [StructLayout(LayoutKind.Sequential)] struct WaveHeader {
        public IntPtr Data;
        public uint BufferLength, BytesRecorded;
        public UIntPtr User;
        public uint Flags, Loops;
        public IntPtr Next;
        public UIntPtr Reserved;
    }
    [DllImport("winmm.dll")] static extern uint waveInOpen(out IntPtr handle, uint device,
        ref WaveFormat format, IntPtr callback, IntPtr instance, uint flags);
    [DllImport("winmm.dll")] static extern uint waveInPrepareHeader(IntPtr handle, IntPtr header, uint size);
    [DllImport("winmm.dll")] static extern uint waveInAddBuffer(IntPtr handle, IntPtr header, uint size);
    [DllImport("winmm.dll")] static extern uint waveInStart(IntPtr handle);
    [DllImport("winmm.dll")] static extern uint waveInReset(IntPtr handle);
    [DllImport("winmm.dll")] static extern uint waveInUnprepareHeader(IntPtr handle, IntPtr header, uint size);
    [DllImport("winmm.dll")] static extern uint waveInClose(IntPtr handle);
    readonly string name;
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    readonly Dictionary<string, object> report = new Dictionary<string, object>();
    const string Payload = "Portable FreeRDP: Romanian șț, German äöü, 日本語";

    PortableIoProbe(string value) {
        foreach(char c in value) if (!Char.IsLetterOrDigit(c) && c!='-') throw new ArgumentException("name");
        name=value;
        Text="WBFreeRDP portable IO "+name;
        Width=480; Height=180;
        Controls.Add(new Label { Text="Testing redirected drive and synthetic audio…", Dock=DockStyle.Fill });
        timer.Interval=1500;
        timer.Tick+=delegate { timer.Stop(); new Thread(Run) { IsBackground=true }.Start(); };
        Shown+=delegate { timer.Start(); };
    }
    void Save() {
        string path="C:\\WBFreeRDP\\portable-io-"+name+".json";
        File.WriteAllText(path+".tmp", new JavaScriptSerializer().Serialize(report));
        if(File.Exists(path)) File.Replace(path+".tmp",path,null);
        else File.Move(path+".tmp",path);
    }
    static void Check(uint code, string operation) {
        if(code!=0) throw new Exception(operation+" failed: "+code);
    }
    static byte[] Tone(int hz) {
        const int rate=44100, samples=rate*2;
        using(MemoryStream stream=new MemoryStream()) {
            using(BinaryWriter w=new BinaryWriter(stream)) {
                w.Write(System.Text.Encoding.ASCII.GetBytes("RIFF")); w.Write(36+samples*2);
                w.Write(System.Text.Encoding.ASCII.GetBytes("WAVEfmt ")); w.Write(16);
                w.Write((ushort)1);w.Write((ushort)1);w.Write(rate);w.Write(rate*2);
                w.Write((ushort)2);w.Write((ushort)16);
                w.Write(System.Text.Encoding.ASCII.GetBytes("data")); w.Write(samples*2);
                for(int i=0;i<samples;i++) w.Write((short)(12000*Math.Sin(2*Math.PI*hz*i/rate)));
                return stream.ToArray();
            }
        }
    }
    void Record() {
        const int rate=44100;
        WaveFormat format=new WaveFormat { FormatTag=1, Channels=1, SamplesPerSec=rate,
            AvgBytesPerSec=rate*2, BlockAlign=2, BitsPerSample=16 };
        IntPtr handle=IntPtr.Zero, data=IntPtr.Zero, header=IntPtr.Zero;
        bool prepared=false;
        uint size=(uint)Marshal.SizeOf(typeof(WaveHeader));
        try {
            Check(waveInOpen(out handle, UInt32.MaxValue, ref format, IntPtr.Zero, IntPtr.Zero, 0),"waveInOpen");
            data=Marshal.AllocHGlobal(rate*2*3);
            header=Marshal.AllocHGlobal((int)size);
            Marshal.StructureToPtr(new WaveHeader { Data=data, BufferLength=rate*2*3 },header,false);
            Check(waveInPrepareHeader(handle,header,size),"waveInPrepareHeader");prepared=true;
            Check(waveInAddBuffer(handle,header,size),"waveInAddBuffer");
            Check(waveInStart(handle),"waveInStart");
            Thread.Sleep(4000);
            Check(waveInReset(handle),"waveInReset");
            WaveHeader result=(WaveHeader)Marshal.PtrToStructure(header,typeof(WaveHeader));
            short[] samples=new short[result.BytesRecorded/2];
            Marshal.Copy(data,samples,0,samples.Length);
            double sum=0;int peak=0,crossings=0;
            for(int i=0;i<samples.Length;i++) {
                sum+=(double)samples[i]*samples[i];peak=Math.Max(peak,Math.Abs((int)samples[i]));
                if(i>0 && samples[i]>=0 && samples[i-1]<0) crossings++;
            }
            report["microphoneSamples"]=samples.Length;
            report["microphoneRms"]=samples.Length>0?Math.Sqrt(sum/samples.Length):0;
            report["microphonePeak"]=peak;
            report["microphonePositiveCrossings"]=crossings;
            if(samples.Length<rate || peak<1000) throw new Exception("Synthetic microphone signal missing");
        } finally {
            if(handle!=IntPtr.Zero) {
                waveInReset(handle);
                if(prepared) waveInUnprepareHeader(handle,header,size);
                waveInClose(handle);
            }
            if(header!=IntPtr.Zero) Marshal.FreeHGlobal(header);
            if(data!=IntPtr.Zero) Marshal.FreeHGlobal(data);
        }
    }
    void Run() {
        try {
            report["pid"]=System.Diagnostics.Process.GetCurrentProcess().Id;
            string shared="\\\\tsclient\\portable\\";
            Exception last=null;
            for(int i=0;i<30;i++) {
                try { if(File.ReadAllText(shared+"from-host.txt")!=Payload) throw new Exception("Drive content mismatch"); last=null;break; }
                catch(Exception error) { last=error;Thread.Sleep(300); }
            }
            if(last!=null) throw last;
            File.WriteAllText(shared+"from-guest.txt",Payload);
            report["driveRoundTrip"]=true;Save();
            using(MemoryStream wav=new MemoryStream(Tone(880)))
                using(SoundPlayer player=new SoundPlayer(wav)) player.PlaySync();
            report["playbackRequested"]=true;Save();
            Record();
            report["pass"]=true;
        } catch(Exception error) { report["pass"]=false;report["error"]=error.ToString(); }
        finally { Save();BeginInvoke((Action)Close); }
    }
    [STAThread] static void Main(string[] args) {
        Application.EnableVisualStyles();
        Application.Run(new PortableIoProbe(args[0]));
    }
}
