# Registry experiment setup error and recovery

During the first PR559 setup on 2026-09-08, the investigation script mistakenly
used `New-Item -Force` on an existing Windows registry key. In this provider that
replaces the key, including its children. The WinStations key lost its existing
values and listener subkeys. The attempt stopped at the now-missing RDP-Tcp key;
the following reboot temporarily disabled RDP. SSH remained available.

This was an error in the investigation script, not a defect in PR559 or FreeRDP.
The initial backup covered all 15 proposed values, but not the whole key tree,
and was insufficient to undo the key replacement by itself.

Recovery used a VSS copy of the guest's SYSTEM hive and transaction logs, with
the open-source YARP registry parser. The deleted WinStations, Console, RDP-Tcp,
TSMMRemotingAllowedApps, and VideoRemotingWindowNames records were recovered.
Of 97 values restored, 87 came from those records (including one recovered from
a transaction log). Ten RDP-Tcp values had been overwritten:

- SelectNetworkDetect, SelectTransport, WdFlag, WdName and WdPrefix were restored
  from this guest's live `Terminal Server\Wds\rdpwd` defaults.
- UserAuthentication was restored to zero, consistent with the successful
  original TLS-only connection. Username and WFProfilePath were set to empty
  strings, and WebSocketListenerPort/WebSocketTlsListenerPort to 3387/3392.

The original values of those last ten entries and deleted per-key ACLs cannot
be proven from the surviving records. Their reconstruction is explicitly not
an exact historical backup. The existing certificate references and security
descriptor *values* in WinStations/Console were recovered from the hive.
Provenance and private recovery artifacts are in `evidence/recovery/`.

All 15 PR559 values/absences were then restored and verified. TermService and
UmRdpService restarted successfully, `qwinsta` listed the RDP listener, and a
fresh TLS RemoteApp test delivered 31.94 visible FPS over 10 seconds with no
invalid markers, backwards frame numbers, or >100 ms stalls. This agrees with
the pre-incident 31.91 FPS baseline, but is not proof that every registry detail
was recovered.

The script was corrected, and the backup covers complete exports of all existing
affected keys, with explicit records for absent keys. Further tests have their
own fresh baseline. On this Windows installation the TermDD service key is absent;
restoration also removes that key if the experiment created it and it is empty.
