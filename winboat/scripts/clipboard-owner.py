#!/usr/bin/env python3
"""Serve controlled UTF-8 text via real ICCCM INCR on an isolated X server."""
from pathlib import Path
import argparse
import hashlib
import json
import select
import time
from Xlib import X,Xatom,display,protocol

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('result',type=Path);parser.add_argument('--display',default=':99')
parser.add_argument('--size',type=int,default=2097152);parser.add_argument('--unicode',action='store_true')
parser.add_argument('--chunk',type=int,default=16384);parser.add_argument('--seconds',type=int,default=45)
args=parser.parse_args()
pattern='WBFreeRDP åéșț😀 ' if args.unicode else 'WBFreeRDP payload '
text=(pattern*((args.size//len(pattern))+1))[:args.size];data=text.encode('utf-8')
x=display.Display(args.display);root=x.screen().root
window=root.create_window(0,0,1,1,0,X.CopyFromParent,X.InputOutput,X.CopyFromParent,event_mask=X.PropertyChangeMask)
selection=x.intern_atom('CLIPBOARD');utf8=x.intern_atom('UTF8_STRING');targets=x.intern_atom('TARGETS');incr=x.intern_atom('INCR')
window.set_selection_owner(selection,X.CurrentTime);x.sync();assert x.get_selection_owner(selection).id==window.id
transfers={};events=[]
metadata={'bytes':len(data),'utf16Units':len(text.encode('utf-16le'))//2,'sha256':hashlib.sha256(data).hexdigest(),
          'chunksSent':0,'completedTransfers':0,'events':events}
def save():args.result.write_text(json.dumps(metadata,indent=2)+'\n')
save();deadline=time.monotonic()+args.seconds
try:
    while time.monotonic()<deadline:
        if not x.pending_events():select.select([x.fileno()],[],[],.1)
        while x.pending_events():
            event=x.next_event()
            if event.type==X.SelectionRequest:
                target=event.target;prop=event.property or target;peer=event.requestor
                if target==targets:
                    peer.change_property(prop,Xatom.ATOM,32,[targets,utf8])
                elif target==utf8:
                    peer.change_attributes(event_mask=X.PropertyChangeMask)
                    peer.change_property(prop,incr,32,[len(data)])
                    transfers[(peer.id,prop)]={'peer':peer,'offset':0}
                    events.append({'event':'start','window':peer.id,'property':prop});save()
                else:prop=X.NONE
                peer.send_event(protocol.event.SelectionNotify(time=event.time,requestor=peer.id,
                    selection=selection,target=target,property=prop),propagate=False)
                x.flush()
            elif event.type==X.PropertyNotify and event.state==X.PropertyDelete:
                key=(event.window.id,event.atom);transfer=transfers.get(key)
                if transfer is None:continue
                start=transfer['offset'];part=data[start:start+args.chunk]
                transfer['peer'].change_property(event.atom,utf8,8,part,X.PropModeAppend)
                x.flush();transfer['offset']+=len(part);metadata['chunksSent']+=1
                if metadata['chunksSent']%16==1:save()
                if not part:
                    metadata['completedTransfers']+=1;events.append({'event':'complete','bytes':start})
                    del transfers[key];save()
            elif event.type==X.SelectionClear:
                events.append({'event':'ownership-lost'})
    save()
finally:x.close()
