using System;
using System.Diagnostics;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
class PaintnetGeometryProbe {
 [StructLayout(LayoutKind.Sequential)] struct Rect {public int left,top,right,bottom;}
 delegate bool EnumProc(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f,IntPtr p);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h,StringBuilder b,int n);
 [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] static extern IntPtr GetWindowLongPtr(IntPtr h,int n);
 [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
 static List<object> Snapshot(){var windows=new List<object>();EnumWindows(delegate(IntPtr h,IntPtr p){uint pid;GetWindowThreadProcessId(h,out pid);try{if(Process.GetProcessById((int)pid).ProcessName!="paintdotnet")return true;}catch{return true;}if(!IsWindowVisible(h))return true;Rect r;GetWindowRect(h,out r);var b=new StringBuilder(512);GetWindowText(h,b,512);windows.Add(new {hwnd=h.ToInt64(),pid=pid,title=b.ToString(),rect=new int[]{r.left,r.top,r.right,r.bottom},style=GetWindowLongPtr(h,-16).ToInt64(),exstyle=GetWindowLongPtr(h,-20).ToInt64()});return true;},IntPtr.Zero);return windows;}
 static int Main(string[] args){if(args.Length!=2||Process.GetCurrentProcess().SessionId==0)return 2;var app=Process.GetProcessesByName("paintdotnet");if(app.Length!=1)return 3;var h=app[0].MainWindowHandle;IntPtr dialog=IntPtr.Zero;EnumWindows(delegate(IntPtr w,IntPtr ignored){uint pid;GetWindowThreadProcessId(w,out pid);if(pid!=app[0].Id)return true;var b=new StringBuilder(512);GetWindowText(w,b,512);if(b.ToString().StartsWith("Untitled - Paint.NET"))h=w;if(b.ToString()=="Layer Properties")dialog=w;return true;},IntPtr.Zero);if(args[0]=="open"){if(dialog!=IntPtr.Zero){PostMessage(dialog,0x10,IntPtr.Zero,IntPtr.Zero);Thread.Sleep(500);}SetForegroundWindow(h);Thread.Sleep(300);PostMessage(h,0x100,(IntPtr)0x73,(IntPtr)1);PostMessage(h,0x101,(IntPtr)0x73,(IntPtr)0xC0000001L);}if(args[0]=="close"){if(dialog!=IntPtr.Zero){PostMessage(dialog,0x10,IntPtr.Zero,IntPtr.Zero);Thread.Sleep(500);}PostMessage(h,0x10,IntPtr.Zero,IntPtr.Zero);}var rows=new List<object>();for(int i=0;i<40;i++){rows.Add(new {ms=i*250,windows=Snapshot()});Thread.Sleep(250);}File.WriteAllText("C:/WBFreeRDP/"+args[1]+".json",new JavaScriptSerializer().Serialize(rows));return 0;}
}
