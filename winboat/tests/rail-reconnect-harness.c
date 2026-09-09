#include <assert.h>
#include <stdio.h>
#include "channels/rail/client/client_rails.c"
static unsigned infos, params, execs;
static BOOL expected_reconnect=FALSE;
static UINT fail_info, fail_params;
static UINT info(RailClientContext* ctx, const RAIL_CLIENT_STATUS_ORDER* order) {
 (void)ctx;assert(!!(order->flags & TS_RAIL_CLIENTSTATUS_AUTORECONNECT)==expected_reconnect);infos++;return fail_info;
}
static UINT param(RailClientContext* ctx, const RAIL_SYSPARAM_ORDER* order) {
 (void)ctx;assert(order->workArea.right==1920);params++;return fail_params;
}
static UINT exec(RailClientContext* ctx, const RAIL_EXEC_ORDER* order) {
 (void)ctx;assert(strcmp(order->RemoteApplicationProgram,"explorer.exe")==0);execs++;return CHANNEL_RC_OK;
}
int main(void) {
 rdpSettings* s=freerdp_settings_new(0);assert(s);
 assert(freerdp_settings_set_bool(s,FreeRDP_AutoReconnectionEnabled,TRUE));
 assert(freerdp_settings_set_bool(s,FreeRDP_RemoteAppLanguageBarSupported,FALSE));
 assert(freerdp_settings_set_uint32(s,FreeRDP_DesktopWidth,1920));
 assert(freerdp_settings_set_string(s,FreeRDP_RemoteApplicationProgram,"explorer.exe"));
 rdpContext rdp={.settings=s};railPlugin plugin={.rdpcontext=&rdp};
 RailClientContext rail={.handle=&plugin,.ClientInformation=info,.ClientSystemParam=param,.ClientExecute=exec};
 assert(client_rail_server_start_cmd(&rail)==CHANNEL_RC_OK);assert(execs==1 && infos==1 && params==1);
 assert(freerdp_settings_set_bool(s,FreeRDP_SessionHasBeenReconnected,TRUE));expected_reconnect=TRUE;
 assert(client_rail_server_start_cmd(&rail)==CHANNEL_RC_OK);assert(execs==1 && infos==2 && params==2);
 assert(client_rail_server_start_cmd(&rail)==CHANNEL_RC_OK);assert(execs==1 && infos==3 && params==3);
 fail_info=ERROR_BAD_CONFIGURATION;assert(client_rail_server_start_cmd(&rail)==ERROR_BAD_CONFIGURATION);assert(params==3 && execs==1);
 fail_info=0;fail_params=ERROR_BAD_CONFIGURATION;assert(client_rail_server_start_cmd(&rail)==ERROR_BAD_CONFIGURATION);assert(execs==1);
 freerdp_settings_free(s);puts("PASS: initial launch, repeated reconnect keeps app, client state resent, channel errors propagated");
}
