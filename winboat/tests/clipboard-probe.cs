using System;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

public class ClipboardProbe : Form {
    readonly Timer timer = new Timer();
    readonly string prefix;
    string last = "";
    public ClipboardProbe(string name) {
        foreach(char c in name) if(!Char.IsLetterOrDigit(c) && c!='-') throw new ArgumentException();
        prefix="C:\\WBFreeRDP\\clip-"+name;
        Text="WBFreeRDP clipboard probe";
        ClientSize=new Size(450,150);
        Controls.Add(new Label { Dock=DockStyle.Fill,Text="Automated clipboard fixture",TextAlign=ContentAlignment.MiddleCenter });
        timer.Interval=200;timer.Tick+=delegate { ProcessCommand(); };timer.Start();
        FormClosed+=delegate { timer.Stop();timer.Dispose(); };
    }
    static string Hash(string value) {
        using(SHA256 sha=SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(value))).Replace("-","").ToLowerInvariant();
    }
    void ProcessCommand() {
        string command;
        try { command=File.ReadAllText(prefix+".command"); } catch(IOException) { return; }
        if(command==last || command.Length==0) return;
        string[] parts=command.Trim().Split(' ');
        if(parts.Length<2) return;
        string id=parts[0], mode=parts[1];
        try {
            string value;
            if(mode=="SET") {
                int size=Int32.Parse(parts[2]);
                value="WBFreeRDP "+new String('x',Math.Max(0,size-14))+" END";
                DataObject data=new DataObject();
                data.SetText(value,TextDataFormat.UnicodeText);
                data.SetText(value,TextDataFormat.Text);
                Clipboard.SetDataObject(data,true);
            } else if(mode=="READ") value=Clipboard.GetText(TextDataFormat.UnicodeText);
            else throw new ArgumentException("Bad command");
            string result="{\"id\":\""+id+"\",\"mode\":\""+mode+"\",\"length\":"+value.Length+",\"sha256\":\""+Hash(value)+"\"}";
            File.WriteAllText(prefix+".json",result,new UTF8Encoding(false));last=command;
        } catch(System.Runtime.InteropServices.ExternalException) { }
    }
    [STAThread] public static void Main(string[] args) {
        Application.EnableVisualStyles();Application.Run(new ClipboardProbe(args[0]));
    }
}
