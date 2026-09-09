using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
using System.Web.Script.Serialization;
class ChipProbe {
 [StructLayout(LayoutKind.Sequential)] struct Rect {public int left,top,right,bottom;}
 delegate bool EnumProc(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc fn,IntPtr p);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h,StringBuilder s,int n);
 [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h,int n);
 [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h,uint n);
 [DllImport("user32.dll",SetLastError=true)] static extern bool GetLayeredWindowAttributes(IntPtr h,out uint key,out byte alpha,out uint flags);
 [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h,uint attr,out uint v,int size);
 static List<object> rows=new List<object>();
 static bool Find(IntPtr h,IntPtr ignored){uint pid;GetWindowThreadProcessId(h,out pid);try{if(Process.GetProcessById((int)pid).ProcessName!="CapCut")return true;}catch{return true;}
 Rect r;GetWindowRect(h,out r);var title=new StringBuilder(1024);var cls=new StringBuilder(256);GetWindowText(h,title,1024);GetClassName(h,cls,256);uint key,flags,cloak;byte alpha;bool layer=GetLayeredWindowAttributes(h,out key,out alpha,out flags);int error=Marshal.GetLastWin32Error();int hr=DwmGetWindowAttribute(h,14,out cloak,4);
 rows.Add(new {pid=pid,hwnd=h.ToInt64().ToString("x"),visible=IsWindowVisible(h),title=title.ToString(),windowClass=cls.ToString(),rect=new int[]{r.left,r.top,r.right,r.bottom},style=((uint)GetWindowLong(h,-16)).ToString("x8"),exStyle=((uint)GetWindowLong(h,-20)).ToString("x8"),owner=GetWindow(h,4).ToInt64().ToString("x"),layeredQuery=layer,layeredError=error,colorKey=key,alpha=alpha,layerFlags=flags,cloakHR=hr,cloaked=cloak});return true;}
 static int Main(){if(Process.GetCurrentProcess().SessionId==0)return 2;EnumWindows(Find,IntPtr.Zero);File.WriteAllText("C:/WBFreeRDP/capcut-chip-windows.json",new JavaScriptSerializer().Serialize(rows));return 0;}
}
