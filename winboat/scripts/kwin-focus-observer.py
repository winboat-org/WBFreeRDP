#!/usr/bin/env python3
import dbus,dbus.service,dbus.mainloop.glib,json,signal
from gi.repository import GLib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=open(ROOT/'evidence/explorer-focus/kwin-events.jsonl','a',buffering=1)
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True);bus=dbus.SessionBus();name=dbus.service.BusName('org.winboat.FocusProbe',bus);last='{}'
class Observer(dbus.service.Object):
 @dbus.service.method('org.winboat.FocusProbe',in_signature='s',out_signature='')
 def Record(self,value):
  global last
  json.loads(value);last=str(value);out.write(last+'\n')
 @dbus.service.method('org.winboat.FocusProbe',in_signature='',out_signature='s')
 def Latest(self):return last
obj=Observer(bus,'/FocusProbe');loop=GLib.MainLoop();signal.signal(signal.SIGTERM,lambda *a:loop.quit());loop.run()
