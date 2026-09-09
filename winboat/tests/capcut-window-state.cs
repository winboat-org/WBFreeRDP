using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
class CapCutWindowState {
 [StructLayout(LayoutKind.Sequential)] struct Rect { public int left,top,right,bottom; }
 [StructLayout(LayoutKind.Sequential)] struct Point { public int x,y; }
 [StructLayout(LayoutKind.Sequential)] struct Placement {public int length,flags,showCmd;public Point min,max;public Rect normal;}
 delegate bool EnumProc(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc fn,IntPtr p);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] static extern bool IsZoomed(IntPtr h);
 [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll")] static extern bool GetWindowPlacement(IntPtr h,ref Placement p);
 [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr h,int command);
 static IntPtr selected=IntPtr.Zero;static long area=0;static uint selectedPid=0;
 static bool Find(IntPtr h,IntPtr ignored){
  if(!IsWindowVisible(h))return true;uint pid;GetWindowThreadProcessId(h,out pid);
  try{if(!String.Equals(Process.GetProcessById((int)pid).ProcessName,"CapCut",StringComparison.OrdinalIgnoreCase))return true;}catch{return true;}
  Rect r;if(!GetWindowRect(h,out r))return true;long a=(long)(r.right-r.left)*(r.bottom-r.top);
  if(a>area){area=a;selected=h;selectedPid=pid;}return true;
 }
 static int Main(string[] args){
  if(args.Length!=2 || (args[0]!="snapshot"&&args[0]!="maximize"&&args[0]!="restore"))return 2;
  if(args[1].IndexOfAny(Path.GetInvalidFileNameChars())>=0 || args[1].Contains(".."))return 2;
  if(Process.GetCurrentProcess().SessionId==0)return 3;
  EnumWindows(Find,IntPtr.Zero);if(selected==IntPtr.Zero)return 4;
  string path="C:/WBFreeRDP/"+args[1]+".json";
  var rows=new StringBuilder("[");var watch=Stopwatch.StartNew();
  if(args[0]!="snapshot"&&!ShowWindowAsync(selected,args[0]=="maximize"?3:9))return 5;
  for(int i=0;i<15;i++){
   Rect r;Placement p=new Placement();p.length=Marshal.SizeOf(typeof(Placement));
   if(!GetWindowRect(selected,out r)||!GetWindowPlacement(selected,ref p))return 6;
   if(i>0)rows.Append(',');
   rows.AppendFormat("{{\"ms\":{0},\"pid\":{1},\"sessionId\":{2},\"hwnd\":\"{3:x}\",\"maximized\":{4},\"showCmd\":{5},\"rect\":[{6},{7},{8},{9}],\"normal\":[{10},{11},{12},{13}]}}",watch.ElapsedMilliseconds,selectedPid,Process.GetCurrentProcess().SessionId,selected.ToInt64(),IsZoomed(selected)?"true":"false",p.showCmd,r.left,r.top,r.right,r.bottom,p.normal.left,p.normal.top,p.normal.right,p.normal.bottom);
   Thread.Sleep(100);
  }
  rows.Append(']');File.WriteAllText(path,rows.ToString(),new UTF8Encoding(false));return 0;
 }
}
