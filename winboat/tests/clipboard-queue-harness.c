#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <winpr/collections.h>
#include <X11/Xlib.h>
#undef WINPR_ASSERT
#define WINPR_ASSERT assert

typedef struct { UINT32 formatToRequest; } RequestedFormat;
typedef struct { XSelectionEvent* expectedResponse; RequestedFormat* requestedFormat; } SelectionResponse;
typedef struct { UINT32 unused; } xfCliprdrFormat;
typedef struct { wArrayList* pending_responses; wArrayList* queued_responses; } xfClipboard;
static unsigned sent[100], sent_count, completed[100], completed_count;
static const xfCliprdrFormat* xf_cliprdr_get_client_format_by_atom(xfClipboard* clip, Atom atom) { static xfCliprdrFormat format; return &format; }
static UINT xf_cliprdr_send_data_request(xfClipboard* clip, UINT32 format, const xfCliprdrFormat* local) { assert(sent_count<100);sent[sent_count++]=format;return 0; }
static void selection_response_free(void* pointer) { SelectionResponse* s=pointer;if(s){free(s->expectedResponse);free(s->requestedFormat);free(s);} }
static void dispatch(xfClipboard* clipboard) {
/* DISPATCH */
}
static void add(xfClipboard* c,unsigned format) {
    SelectionResponse* s=calloc(1,sizeof(*s));assert(s);
    s->expectedResponse=calloc(1,sizeof(*s->expectedResponse));assert(s->expectedResponse);
    s->requestedFormat=calloc(1,sizeof(*s->requestedFormat));assert(s->requestedFormat);
    s->requestedFormat->formatToRequest=format;s->expectedResponse->target=format;
    assert(ArrayList_Append(c->queued_responses,s));
}
int main(int argc,char** argv) {
    xfClipboard c={ArrayList_New(TRUE),ArrayList_New(TRUE)};assert(c.pending_responses&&c.queued_responses);
    ArrayList_Object(c.pending_responses)->fnObjectFree=selection_response_free;
    ArrayList_Object(c.queued_responses)->fnObjectFree=selection_response_free;
    for(int i=1;i<argc;i++)add(&c,(unsigned)atoi(argv[i]));
    for(unsigned round=0;round<8;round++){
        dispatch(&c);
        for(size_t i=0;i<(size_t)ArrayList_Count(c.pending_responses);i++){
            SelectionResponse* s=ArrayList_GetItem(c.pending_responses,i);
            assert(completed_count<100);completed[completed_count++]=s->requestedFormat->formatToRequest;
        }
        ArrayList_Clear(c.pending_responses);
        if(!ArrayList_Count(c.queued_responses))break;
    }
    printf("{\"queued\":%zu,\"sent\":[",ArrayList_Count(c.queued_responses));
    for(unsigned i=0;i<sent_count;i++)printf("%s%u",i?",":"",sent[i]);
    printf("],\"completed\":[");for(unsigned i=0;i<completed_count;i++)printf("%s%u",i?",":"",completed[i]);puts("]}");
    ArrayList_Free(c.pending_responses);ArrayList_Free(c.queued_responses);return 0;
}
