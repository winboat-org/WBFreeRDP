using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Web.Script.Serialization;
class ExplorerFocusProbe {
 [StructLayout(LayoutKind.Sequential)] struct Rect {public int left,top,right,bottom;}
 [StructLayout(LayoutKind.Sequential)] struct Gui {public int size;public uint flags; public IntPtr active,focus,capture,menuOwner,moveSize,caret;public Rect caretRect;}
 delegate bool EnumProc(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc fn,IntPtr p);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h,uint flags);
 [DllImport("user32.dll")] static extern bool GetGUIThreadInfo(uint thread,ref Gui g);
 static JavaScriptSerializer ser=new JavaScriptSerializer();static List<object> wins=new List<object>();
 static string Id(IntPtr h){return h.ToInt64().ToString("x");}
 static object Info(IntPtr h){uint pid;uint tid=GetWindowThreadProcessId(h,out pid);var title=new StringBuilder(1024);var cls=new StringBuilder(256);GetWindowText(h,title,1024);GetClassName(h,cls,256);Rect r;GetWindowRect(h,out r);return new{hwnd=Id(h),pid=pid,tid=tid,title=title.ToString(),windowClass=cls.ToString(),rect=new int[]{r.left,r.top,r.right,r.bottom}};}
 static bool Find(IntPtr h,IntPtr p){if(!IsWindowVisible(h))return true;uint pid;GetWindowThreadProcessId(h,out pid);try{string n=Process.GetProcessById((int)pid).ProcessName;if(n=="explorer"||n=="CapCut")wins.Add(Info(h));}catch{}return true;}
 static int Main(string[] args){if(args.Length!=2||Process.GetCurrentProcess().SessionId==0)return 2;int duration;if(!int.TryParse(args[1],out duration)||duration<1||duration>180)return 3;if(args[0].IndexOfAny(Path.GetInvalidFileNameChars())>=0||args[0].Contains(".."))return 4;
 using(var f=new StreamWriter("C:/WBFreeRDP/"+args[0]+".jsonl",false,new UTF8Encoding(false))){f.AutoFlush=true;EnumWindows(Find,IntPtr.Zero);f.WriteLine(ser.Serialize(new{kind="windows",utc=DateTime.UtcNow.ToString("o"),session=Process.GetCurrentProcess().SessionId,windows=wins}));var sw=Stopwatch.StartNew();string last=null;while(sw.ElapsedMilliseconds<duration*1000){Gui g=new Gui();g.size=Marshal.SizeOf(typeof(Gui));bool ok=GetGUIThreadInfo(0,ref g);var fg=GetForegroundWindow();string state=ser.Serialize(new{foreground=Info(fg),guiOk=ok,active=Id(g.active),focus=Id(g.focus),focusRoot=Id(GetAncestor(g.focus,2)),capture=Id(g.capture),menu=Id(g.menuOwner),flags=g.flags});if(state!=last){f.WriteLine("{\"kind\":\"focus\",\"utc\":\""+DateTime.UtcNow.ToString("o")+"\",\"ms\":"+sw.ElapsedMilliseconds+",\"state\":"+state+"}");last=state;}Thread.Sleep(20);}wins.Clear();EnumWindows(Find,IntPtr.Zero);f.WriteLine(ser.Serialize(new{kind="end-windows",utc=DateTime.UtcNow.ToString("o"),windows=wins}));f.WriteLine(ser.Serialize(new{kind="done",utc=DateTime.UtcNow.ToString("o")}));}return 0;}
}
