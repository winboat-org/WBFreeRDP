#include <windows.h>
#include <mmsystem.h>
#include <stdint.h>

static uint32_t pixels[1280 * 720];
static unsigned frame;
static void render(void)
{
    for (unsigned y = 0; y < 720; y++)
        for (unsigned x = 0; x < 1280; x++)
        {
            unsigned r = (x + frame * 5) & 255;
            unsigned g = (y + frame * 3) & 255;
            unsigned b = ((x + y) / 3 + frame * 7) & 255;
            uint32_t color = 0xff000000 | (r << 16) | (g << 8) | b;
            if (y < 20 && x < 20)
                color = 0xffff00ff;
            else if (y < 40 && x >= 20 && x < 340)
            {
                unsigned bit = (x - 20) / 20;
                unsigned white = ((frame >> bit) & 1) ^ (y >= 20);
                color = white ? 0xffffffff : 0xff000000;
            }
            pixels[y * 1280 + x] = color;
        }
}
static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wparam, LPARAM lparam)
{
    switch (message)
    {
        case WM_CREATE:
            SetTimer(window, 1, 10, NULL);
            SetTimer(window, 2, 90000, NULL);
            return 0;
        case WM_TIMER:
            if (wparam == 2)
                DestroyWindow(window);
            else
            {
                frame++;
                render();
                InvalidateRect(window, NULL, FALSE);
                UpdateWindow(window);
            }
            return 0;
        case WM_ERASEBKGND:
            return 1;
        case WM_PAINT:
        {
            PAINTSTRUCT paint;
            HDC dc = BeginPaint(window, &paint);
            BITMAPINFO bitmap = { 0 };
            bitmap.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
            bitmap.bmiHeader.biWidth = 1280;
            bitmap.bmiHeader.biHeight = -720;
            bitmap.bmiHeader.biPlanes = 1;
            bitmap.bmiHeader.biBitCount = 32;
            SetDIBitsToDevice(dc, 0, 0, 1280, 720, 0, 0, 0, 720, pixels, &bitmap, DIB_RGB_COLORS);
            EndPaint(window, &paint);
            return 0;
        }
        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProcW(window, message, wparam, lparam);
}
int WINAPI WinMain(HINSTANCE instance, HINSTANCE previous, LPSTR command, int show)
{
    (void)previous; (void)command; (void)show;
    timeBeginPeriod(1);
    WNDCLASSW klass = { 0 };
    klass.lpfnWndProc = window_proc;
    klass.hInstance = instance;
    klass.lpszClassName = L"WBFreeRDPFrameProbe";
    klass.hCursor = LoadCursor(NULL, IDC_ARROW);
    if (!RegisterClassW(&klass))
        return 1;
    RECT size = { 0, 0, 1280, 720 };
    AdjustWindowRect(&size, WS_OVERLAPPEDWINDOW, FALSE);
    HWND window = CreateWindowW(klass.lpszClassName, L"WBFreeRDP frame probe", WS_OVERLAPPEDWINDOW,
        160, 100, size.right - size.left, size.bottom - size.top, NULL, NULL, instance, NULL);
    if (!window)
        return 2;
    ShowWindow(window, SW_SHOW);
    MSG message;
    while (GetMessageW(&message, NULL, 0, 0) > 0)
    {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    timeEndPeriod(1);
    return 0;
}
