using System;
using System.IO;
using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;
using System.Web.Script.Serialization;
class IssueDragProbe : Form {
 int downs,ups,moves,capturedMoves; string prefix; DateTime start=DateTime.UtcNow;
 public IssueDragProbe(string label){prefix="C:/WBFreeRDP/"+label;Text="WBFreeRDP Drag Fixture";StartPosition=FormStartPosition.Manual;Bounds=new Rectangle(420,320,700,380);BackColor=Color.LightSteelBlue;
 MouseDown+=delegate(object sender,MouseEventArgs e){if(e.Button==MouseButtons.Left)downs++;};MouseUp+=delegate(object sender,MouseEventArgs e){if(e.Button==MouseButtons.Left)ups++;};MouseMove+=delegate(object sender,MouseEventArgs e){if(e.Button==MouseButtons.Left){moves++;if(Capture)capturedMoves++;}};
 var timer=new Timer();timer.Interval=100;timer.Tick+=delegate{File.WriteAllText(prefix+".json",new JavaScriptSerializer().Serialize(new {pid=Process.GetCurrentProcess().Id,downs=downs,ups=ups,moves=moves,capturedMoves=capturedMoves}));if((DateTime.UtcNow-start).TotalSeconds>60||File.Exists(prefix+".stop"))Close();};timer.Start();}
 [STAThread] static void Main(string[] args){if(args.Length!=1||Process.GetCurrentProcess().SessionId==0)return;Application.EnableVisualStyles();Application.Run(new IssueDragProbe(args[0]));}
}
