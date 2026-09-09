using System;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Web.Script.Serialization;
class IssueClipboardProbe {
 [DllImport("user32.dll")] static extern bool OpenClipboard(IntPtr owner);
 [DllImport("user32.dll")] static extern bool CloseClipboard();
 [DllImport("user32.dll")] static extern IntPtr GetClipboardData(uint format);
 [DllImport("kernel32.dll")] static extern IntPtr GlobalLock(IntPtr h);
 [DllImport("kernel32.dll")] static extern bool GlobalUnlock(IntPtr h);
 [DllImport("kernel32.dll")] static extern UIntPtr GlobalSize(IntPtr h);
 static byte[] ReadDib(){
  if(!OpenClipboard(IntPtr.Zero))throw new ExternalException("Clipboard busy");
  try{IntPtr h=GetClipboardData(8);if(h==IntPtr.Zero)return null;ulong size=GlobalSize(h).ToUInt64();if(size>33554432)throw new Exception("DIB too large");IntPtr mem=GlobalLock(h);if(mem==IntPtr.Zero)return null;try{byte[] b=new byte[(int)size];Marshal.Copy(mem,b,0,b.Length);return b;}finally{GlobalUnlock(h);}}
  finally{CloseClipboard();}
 }
 static object InspectDib(string id,string[]formats){
  byte[] dib=ReadDib();if(dib==null||dib.Length<40)return new{id=id,hasImage=false,formats=formats,dibBytes=dib==null?0:dib.Length};
  int header=BitConverter.ToInt32(dib,0),w=BitConverter.ToInt32(dib,4),h=BitConverter.ToInt32(dib,8),bits=BitConverter.ToUInt16(dib,14),compression=BitConverter.ToInt32(dib,16);
  if(w<=0||h==0||w>4096||Math.Abs(h)>4096||(bits!=24&&bits!=32)||compression!=0)return new{id=id,hasImage=false,formats=formats,dibBytes=dib.Length,header=header,width=w,height=h,bits=bits,compression=compression};
  int height=Math.Abs(h),stride=((w*bits+31)/32)*4;byte[] pixels=new byte[w*height*4];int n=0;
  for(int y=0;y<height;y++)for(int x=0;x<w;x++){int i=header+(h>0?height-1-y:y)*stride+x*(bits/8);pixels[n++]=dib[i+2];pixels[n++]=dib[i+1];pixels[n++]=dib[i];pixels[n++]=255;}
  return new{id=id,hasImage=true,width=w,height=height,sha256=Hash(pixels),formats=formats,dibBytes=dib.Length,bits=bits};
 }
 static string prefix,last="";static Timer timer;static DateTime end;
 static JavaScriptSerializer json=new JavaScriptSerializer();
 static string Hash(byte[] b){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(b)).Replace("-","").ToLowerInvariant();}
 static void Tick(object sender,EventArgs e){
  if(DateTime.UtcNow>end){Application.ExitThread();return;}
  string cmd;try{cmd=File.ReadAllText(prefix+".command").Trim();}catch(IOException){return;}if(cmd==last||cmd.Length==0)return;
  string[] parts=cmd.Split(' ');string id=parts[0];
  try {
   object result;
   if(parts[1]=="READ_IMAGE"){
    IDataObject data=Clipboard.GetDataObject();string[] formats=data==null?new string[0]:data.GetFormats(false);
    result=InspectDib(id,formats);
   }else if((parts[1]=="SET_PRIVATE"||parts[1]=="SET_PRIVATE_ONLY")){
    var d=new DataObject();d.SetData("WBFreeRDP.PrivateClipboardProbe",false,new MemoryStream(Encoding.ASCII.GetBytes("WBFreeRDP private payload v1")));if(parts[1]=="SET_PRIVATE")d.SetText("WBFreeRDP private-format companion text");Clipboard.SetDataObject(d,true);result=new{id=id,set=true};
   }else if(parts[1]=="READ_PRIVATE"){
    var d=Clipboard.GetDataObject();var v=d==null?null:d.GetData("WBFreeRDP.PrivateClipboardProbe",false);byte[] b=null;
    if(v is MemoryStream)b=((MemoryStream)v).ToArray();else if(v is byte[])b=(byte[])v;
    result=new{id=id,hasPrivate=b!=null,sha256=b==null?null:Hash(b),formats=d==null?new string[0]:d.GetFormats(false)};
   }else if(parts[1]=="EXIT"){Application.ExitThread();return;}else throw new ArgumentException("unknown command");
   File.WriteAllText(prefix+".json",json.Serialize(result));last=cmd;
  }catch(System.Runtime.InteropServices.ExternalException){}catch(Exception ex){File.WriteAllText(prefix+".json",json.Serialize(new{id=id,error=ex.GetType().Name,message=ex.Message}));last=cmd;}
 }
 [STAThread] static int Main(string[] args){if(args.Length!=1)return 2;foreach(char c in args[0])if(!Char.IsLetterOrDigit(c)&&c!='-')return 2;
 prefix="C:/WBFreeRDP/issue-clip-"+args[0];end=DateTime.UtcNow.AddMinutes(4);timer=new Timer();timer.Interval=100;timer.Tick+=Tick;timer.Start();File.WriteAllText(prefix+".ready","ready");Application.Run();timer.Dispose();return 0;}
}
