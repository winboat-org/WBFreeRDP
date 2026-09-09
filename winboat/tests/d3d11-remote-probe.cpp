// D3D11 -> staging readback -> RemoteApp pixel correctness fixture.
// All graphics work runs in the interactive RDP session that launches this app.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <d3dcompiler.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <stdexcept>
#include <fstream>

namespace {
template<class T> struct Com {
    T* p=nullptr;
    ~Com(){ reset(); }
    void reset(){ if(p){p->Release();p=nullptr;} }
    T* operator->()const{return p;}
    T** out(){reset();return &p;}
    Com()=default; Com(const Com&)=delete; Com& operator=(const Com&)=delete;
};
std::string output,commandPath;
HWND window=nullptr;
unsigned width=720,height=480,frame=0,resizes=0,checks=0;
unsigned checkedFrame=0;
uint64_t checkedPixels=0,mismatches=0;
unsigned mismatchX=0,mismatchY=0,mismatchExpected=0,mismatchActual=0,readbackRowPitch=0;
bool resizePending=false;
HRESULT lastHr=S_OK;
std::string failure;
DXGI_ADAPTER_DESC adapterDesc={};
unsigned featureLevel=0;
DWORD sessionId=0;
void require(HRESULT hr,const char* operation){
    lastHr=hr;
    if(FAILED(hr)){char message[180];snprintf(message,sizeof(message),"%s: 0x%08lx",operation,(unsigned long)hr);throw std::runtime_error(message);}
}
void snapshot(bool frozen){
    char adapter[512]={};
    WideCharToMultiByte(CP_UTF8,0,adapterDesc.Description,-1,adapter,sizeof(adapter),nullptr,nullptr);
    // Adapter names are diagnostic text; escape JSON quotes and slashes.
    std::string description;
    for(char c:std::string(adapter)){if(c=='"'||c=='\\')description+='\\';if((unsigned char)c>=32)description+=c;}
    RECT outer={};GetWindowRect(window,&outer);
    std::string temp=output+".tmp";
    FILE* file=fopen(temp.c_str(),"wb");
    if(!file) return;
    fprintf(file,"{\"pid\":%lu,\"sessionId\":%lu,\"hwnd\":\"%llx\",\"frame\":%u,\"width\":%u,\"height\":%u,"
        "\"outerWidth\":%ld,\"outerHeight\":%ld,\"resizes\":%u,\"readbackChecks\":%u,\"checkedFrame\":%u,"
        "\"checkedPixels\":%llu,\"mismatches\":%llu,\"frozen\":%s,\"adapter\":\"%s\",\"vendorId\":%u,"
        "\"deviceId\":%u,\"featureLevel\":%u,\"lastHr\":%lu,\"error\":\"%s\",\"readbackRowPitch\":%u,\"firstMismatch\":{\"x\":%u,\"y\":%u,\"expectedBGRA\":%u,\"actualBGRA\":%u}}\n",
        GetCurrentProcessId(),sessionId,(unsigned long long)(uintptr_t)window,frame,width,height,
        outer.right-outer.left,outer.bottom-outer.top,resizes,checks,checkedFrame,
        (unsigned long long)checkedPixels,(unsigned long long)mismatches,frozen?"true":"false",description.c_str(),
        adapterDesc.VendorId,adapterDesc.DeviceId,featureLevel,(unsigned long)lastHr,failure.c_str(),readbackRowPitch,
        mismatchX,mismatchY,mismatchExpected,mismatchActual);
    fclose(file);
    MoveFileExA(temp.c_str(),output.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
}
LRESULT CALLBACK wndproc(HWND h,UINT m,WPARAM w,LPARAM l){
    if(m==WM_SIZE && w!=SIZE_MINIMIZED){unsigned ww=LOWORD(l),hh=HIWORD(l);if(ww&&hh&&(ww!=width||hh!=height)){width=ww;height=hh;resizePending=true;}return 0;}
    if(m==WM_GETMINMAXINFO){auto* info=(MINMAXINFO*)l;info->ptMinTrackSize={400,240};return 0;}
    if(m==WM_DESTROY){PostQuitMessage(0);return 0;}
    return DefWindowProcW(h,m,w,l);
}
uint32_t expected(unsigned x,unsigned y,unsigned serial){
    if(y<32){
        if(x<16) return 0xffff00ff;
        if(x<272){bool white=((serial>>((x-16)/8))&1)^(y>=16);return white?0xffffffff:0xff000000;}
        return 0xff304050;
    }
    if(x>=width-16&&y>=height-16) return 0xffffff00;
    unsigned r=((x/32+serial)%8)*32+16,g=((y/32)%8)*32+16,b=((x/32+y/32+serial)%8)*32+16;
    return 0xff000000|(r<<16)|(g<<8)|b;
}
const char* shader=R"HLSL(
cbuffer State:register(b0){uint serial;uint width;uint height;uint unused;};
float4 vs(uint id:SV_VertexID):SV_Position{
    float2 p=float2((id<<1)&2,id&2);return float4(p*float2(2,-2)+float2(-1,1),0,1);
}
float4 ps(float4 p:SV_Position):SV_Target{
    uint x=(uint)p.x,y=(uint)p.y;
    if(y<32){
        if(x<16)return float4(1,0,1,1);
        if(x<272){uint a=((serial>>((x-16)/8))&1)^(uint)(y>=16);return float4(a,a,a,1);}
        return float4(48,64,80,255)/255;
    }
    if(x>=width-16&&y>=height-16)return float4(1,1,0,1);
    return float4(((x/32+serial)%8)*32+16,((y/32)%8)*32+16,((x/32+y/32+serial)%8)*32+16,255)/255;
}
)HLSL";
}
int main(int argc,char** argv){
    // Pure compiler check: safe outside an interactive graphics session.
    if(argc==2 && !strcmp(argv[1],"--check-shaders")){
        for(const char* entry:{"vs","ps"}){
            Com<ID3DBlob> code,errors;
            HRESULT hr=D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,entry,
                !strcmp(entry,"vs")?"vs_4_0":"ps_4_0",0,0,code.out(),errors.out());
            if(FAILED(hr)){
                fprintf(stderr,"%s shader failed: 0x%08lx\n%s\n",entry,(unsigned long)hr,
                    errors.p?(char*)errors->GetBufferPointer():"");return 1;
            }
            printf("%s shader compiled: %llu bytes\n",entry,(unsigned long long)code->GetBufferSize());
        }
        return 0;
    }
    if(argc!=4)return 2;
    std::string name=argv[1],choice=argv[2],swap=argv[3];
    if(name.empty()||name.size()>80||name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")!=std::string::npos)return 2;
    if((choice!="default"&&choice!="helios"&&choice!="warp")||(swap!="flip"&&swap!="blt"))return 2;
    output="C:/WBFreeRDP/d3d11-"+name+".json";commandPath="C:/WBFreeRDP/d3d11-"+name+".command";
    SetProcessDPIAware();ProcessIdToSessionId(GetCurrentProcessId(),&sessionId);
    try{
        WNDCLASSW wc={};wc.lpfnWndProc=wndproc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"WBFreeRDPD3D11";wc.hCursor=LoadCursor(nullptr,IDC_ARROW);
        if(!RegisterClassW(&wc))throw std::runtime_error("RegisterClass failed");
        RECT r={0,0,(LONG)width,(LONG)height};AdjustWindowRect(&r,WS_OVERLAPPEDWINDOW,FALSE);
        std::wstring title=L"WBFreeRDP D3D11 "+std::wstring(name.begin(),name.end());
        window=CreateWindowW(wc.lpszClassName,title.c_str(),WS_OVERLAPPEDWINDOW,100,80,r.right-r.left,r.bottom-r.top,nullptr,nullptr,wc.hInstance,nullptr);
        if(!window)throw std::runtime_error("CreateWindow failed");
        ShowWindow(window,SW_SHOW);UpdateWindow(window);
        Com<IDXGIFactory2> factory;require(CreateDXGIFactory1(__uuidof(IDXGIFactory2),(void**)factory.out()),"CreateDXGIFactory1");
        Com<IDXGIAdapter1> chosen;
        if(choice=="helios"){
            for(UINT i=0;;i++){
                Com<IDXGIAdapter1> candidate;HRESULT hr=factory->EnumAdapters1(i,candidate.out());
                if(hr==DXGI_ERROR_NOT_FOUND)break;require(hr,"EnumAdapters1");
                DXGI_ADAPTER_DESC1 d={};require(candidate->GetDesc1(&d),"GetDesc1");
                if(wcsstr(d.Description,L"Helios")){chosen.p=candidate.p;candidate.p=nullptr;break;}
            }
            if(!chosen.p)throw std::runtime_error("Helios adapter not enumerated");
        }
        Com<ID3D11Device> device;Com<ID3D11DeviceContext> context;
        D3D_FEATURE_LEVEL levels[]={D3D_FEATURE_LEVEL_11_1,D3D_FEATURE_LEVEL_11_0};D3D_FEATURE_LEVEL got;
        D3D_DRIVER_TYPE type=chosen.p?D3D_DRIVER_TYPE_UNKNOWN:choice=="warp"?D3D_DRIVER_TYPE_WARP:D3D_DRIVER_TYPE_HARDWARE;
        require(D3D11CreateDevice(chosen.p,type,nullptr,D3D11_CREATE_DEVICE_BGRA_SUPPORT,levels,2,D3D11_SDK_VERSION,device.out(),&got,context.out()),"D3D11CreateDevice");featureLevel=(unsigned)got;
        Com<IDXGIDevice> dxgiDevice;Com<IDXGIAdapter> actual;
        require(device->QueryInterface(__uuidof(IDXGIDevice),(void**)dxgiDevice.out()),"Query DXGI device");
        require(dxgiDevice->GetAdapter(actual.out()),"GetAdapter");require(actual->GetDesc(&adapterDesc),"GetDesc");
        DXGI_SWAP_CHAIN_DESC1 sd={};sd.Width=width;sd.Height=height;sd.Format=DXGI_FORMAT_B8G8R8A8_UNORM;
        sd.SampleDesc.Count=1;sd.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;sd.BufferCount=swap=="flip"?2:1;
        sd.SwapEffect=swap=="flip"?DXGI_SWAP_EFFECT_FLIP_DISCARD:DXGI_SWAP_EFFECT_DISCARD;sd.AlphaMode=DXGI_ALPHA_MODE_IGNORE;
        Com<IDXGISwapChain1> chain;require(factory->CreateSwapChainForHwnd(device.p,window,&sd,nullptr,nullptr,chain.out()),"CreateSwapChainForHwnd");
        require(factory->MakeWindowAssociation(window,DXGI_MWA_NO_ALT_ENTER),"MakeWindowAssociation");
        Com<ID3DBlob> vsCode,psCode,errors;
        require(D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,"vs","vs_4_0",0,0,vsCode.out(),errors.out()),"Compile vertex shader");
        require(D3DCompile(shader,strlen(shader),nullptr,nullptr,nullptr,"ps","ps_4_0",0,0,psCode.out(),errors.out()),"Compile pixel shader");
        Com<ID3D11VertexShader> vs;Com<ID3D11PixelShader> ps;
        require(device->CreateVertexShader(vsCode->GetBufferPointer(),vsCode->GetBufferSize(),nullptr,vs.out()),"CreateVertexShader");
        require(device->CreatePixelShader(psCode->GetBufferPointer(),psCode->GetBufferSize(),nullptr,ps.out()),"CreatePixelShader");
        D3D11_BUFFER_DESC bd={};bd.ByteWidth=16;bd.Usage=D3D11_USAGE_DEFAULT;bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
        Com<ID3D11Buffer> state;require(device->CreateBuffer(&bd,nullptr,state.out()),"Create constant buffer");
        Com<ID3D11Texture2D> back,staging;Com<ID3D11RenderTargetView> target;
        auto buffers=[&](){
            require(chain->GetBuffer(0,__uuidof(ID3D11Texture2D),(void**)back.out()),"GetBuffer");
            require(device->CreateRenderTargetView(back.p,nullptr,target.out()),"CreateRenderTargetView");
            D3D11_TEXTURE2D_DESC td={};back->GetDesc(&td);td.Usage=D3D11_USAGE_STAGING;td.BindFlags=0;td.CPUAccessFlags=D3D11_CPU_ACCESS_READ;td.MiscFlags=0;
            require(device->CreateTexture2D(&td,nullptr,staging.out()),"Create staging texture");
        };
        buffers();resizePending=false;
        ULONGLONG began=GetTickCount64(),lastSnapshot=0;unsigned draws=0;
        while(GetTickCount64()-began<180000){
            MSG msg;bool quit=false;
            while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){if(msg.message==WM_QUIT){quit=true;break;}TranslateMessage(&msg);DispatchMessageW(&msg);}
            if(quit)break;
            std::ifstream command(commandPath);std::string action;command>>action;bool frozen=action=="freeze";
            if(action=="quit")break;
            if(resizePending){
                context->ClearState();target.reset();back.reset();staging.reset();
                require(chain->ResizeBuffers(0,width,height,DXGI_FORMAT_UNKNOWN,0),"ResizeBuffers");
                buffers();resizePending=false;resizes++;
            }
            if(!frozen)frame++;
            unsigned data[]={frame,width,height,0};context->UpdateSubresource(state.p,0,nullptr,data,0,0);
            context->OMSetRenderTargets(1,&target.p,nullptr);
            D3D11_VIEWPORT vp={0,0,(float)width,(float)height,0,1};context->RSSetViewports(1,&vp);
            context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            context->VSSetShader(vs.p,nullptr,0);context->PSSetShader(ps.p,nullptr,0);context->PSSetConstantBuffers(0,1,&state.p);
            context->Draw(3,0);
            if(draws%15==0||frozen){
                context->CopyResource(staging.p,back.p);D3D11_MAPPED_SUBRESOURCE map={};
                require(context->Map(staging.p,0,D3D11_MAP_READ,0,&map),"Map staging");
                readbackRowPitch=map.RowPitch;
                for(unsigned y=0;y<height;y++)for(unsigned x=0;x<width;x++){
                    const uint8_t* pixel=(const uint8_t*)map.pData+(size_t)y*map.RowPitch+x*4;
                    uint32_t want=expected(x,y,frame);
                    for(unsigned channel=0;channel<4;channel++)if(abs((int)pixel[channel]-(int)((want>>(channel*8))&255))>1){
                        if(!mismatches){mismatchX=x;mismatchY=y;mismatchExpected=want;memcpy(&mismatchActual,pixel,4);}
                        mismatches++;break;
                    }
                }
                context->Unmap(staging.p,0);checks++;checkedFrame=frame;checkedPixels+=(uint64_t)width*height;
                if(mismatches)throw std::runtime_error("GPU readback pixel mismatch");
            }
            HRESULT present=chain->Present(1,0);require(present,"Present");draws++;
            if(GetTickCount64()-lastSnapshot>=250){snapshot(frozen);lastSnapshot=GetTickCount64();}
            Sleep(20);
        }
        context->ClearState();context->Flush();snapshot(false);
        DestroyWindow(window);return 0;
    }catch(const std::exception& e){failure=e.what();snapshot(false);if(window)DestroyWindow(window);return 1;}
}
