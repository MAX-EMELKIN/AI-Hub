# -*- coding: utf-8 -*-
# data/core/hotkey_manager.py

import ctypes, re, threading, time
from ctypes import wintypes
user32 =ctypes .windll .user32
kernel32 =ctypes .windll .kernel32

if ctypes .sizeof (ctypes .c_void_p )==8 :
    LRESULT =ctypes .c_int64
    WPARAM =ctypes .c_uint64
    LPARAM =ctypes .c_int64
    ULONG_PTR =ctypes .c_uint64
else :
    LRESULT =ctypes .c_long
    WPARAM =ctypes .c_uint
    LPARAM =ctypes .c_long
    ULONG_PTR =ctypes .c_ulong

HOOKPROC =ctypes .WINFUNCTYPE (LRESULT ,ctypes .c_int ,WPARAM ,LPARAM )

kernel32 .GetModuleHandleW .argtypes =[wintypes .LPCWSTR ]
kernel32 .GetModuleHandleW .restype =wintypes .HINSTANCE

user32 .SetWindowsHookExW .argtypes =[ctypes .c_int ,HOOKPROC ,wintypes .HINSTANCE ,wintypes .DWORD ]
user32 .SetWindowsHookExW .restype =wintypes .HHOOK

user32 .CallNextHookEx .argtypes =[wintypes .HHOOK ,ctypes .c_int ,WPARAM ,LPARAM ]
user32 .CallNextHookEx .restype =LRESULT

user32 .UnhookWindowsHookEx .argtypes =[wintypes .HHOOK ]
user32 .UnhookWindowsHookEx .restype =wintypes .BOOL

user32 .GetAsyncKeyState .argtypes =[ctypes .c_int ]
user32 .GetAsyncKeyState .restype =ctypes .c_short

user32 .GetForegroundWindow .argtypes =[]
user32 .GetForegroundWindow .restype =wintypes .HWND

user32 .GetWindowTextLengthW .argtypes =[wintypes .HWND ]
user32 .GetWindowTextLengthW .restype =ctypes .c_int

user32 .GetClassNameW .argtypes =[wintypes .HWND ,wintypes .LPWSTR ,ctypes .c_int ]
user32 .GetClassNameW .restype =ctypes .c_int

WH_KEYBOARD_LL =13
WM_KEYDOWN =0x0100
WM_SYSKEYDOWN =0x0104

class KBDLLHOOKSTRUCT (ctypes .Structure ):
    _fields_ =[
    ('vkCode',wintypes .DWORD ),
    ('scanCode',wintypes .DWORD ),
    ('flags',wintypes .DWORD ),
    ('time',wintypes .DWORD ),
    ('dwExtraInfo',ULONG_PTR )
    ]

VK_MAP ={
"f1":0x70 ,"f2":0x71 ,"f3":0x72 ,"f4":0x73 ,"f5":0x74 ,"f6":0x75 ,
"f7":0x76 ,"f8":0x77 ,"f9":0x78 ,"f10":0x79 ,"f11":0x7A ,"f12":0x7B ,
"q":0x51 ,"w":0x57 ,"e":0x45 ,"r":0x52 ,"t":0x54 ,"y":0x59 ,"u":0x55 ,
"i":0x49 ,"o":0x4F ,"p":0x50 ,"a":0x41 ,"s":0x53 ,"d":0x44 ,"f":0x46 ,
"g":0x47 ,"h":0x48 ,"j":0x4A ,"k":0x4B ,"l":0x4C ,"z":0x5A ,"x":0x58 ,
"c":0x43 ,"v":0x56 ,"b":0x42 ,"n":0x4E ,"m":0x4D ,"space":0x20 ,"tab":0x09 ,
"esc":0x1B ,"escape":0x1B ,"enter":0x0D ,"return":0x0D ,
"1":0x31 ,"2":0x32 ,"3":0x33 ,"4":0x34 ,"5":0x35 ,"6":0x36 ,"7":0x37 ,"8":0x38 ,"9":0x39 ,"0":0x30
}

SYSTEM_IGNORE_CLASSES =[
"shell_traywnd","progman","workerw","qtranslateaihubtray",
"shell_secondarytraywnd","cortana","windows.ui.core.corewindow"
]

class ActiveWindowTracker :
    def __init__ (self ):
        self .last_user_hwnd =None
        self ._running =True
        self ._thread =threading .Thread (target =self ._loop ,daemon =True )
        self ._thread .start ()

    def _loop (self ):
        while self ._running :
            try :
                h =user32 .GetForegroundWindow ()
                if h :
                    buf =(ctypes .c_wchar *256 )()
                    user32 .GetClassNameW (h ,buf ,256 )
                    c_name =buf .value .lower ()

                    if not any (bad in c_name for bad in SYSTEM_IGNORE_CLASSES ):
                        if user32 .GetWindowTextLengthW (h )>0 :
                            self .last_user_hwnd =h
            except Exception :pass
            time .sleep (0.05 )

window_tracker =ActiveWindowTracker ()

class GlobalHotkeyManager :
    def __init__ (self ):
        self .hook_handle =None
        self .main_window =None
        self ._hook_ref =HOOKPROC (self ._hook_callback )

        self .ocr_hotkey_parsed =None
        self .toggle_hotkey_parsed =None
        self .tts_hotkey_parsed =None

        self ._last_ctrl_time =0
        self ._last_alt_time =0

    def parse_hotkey (self ,hotkey_str ):
        h =str (hotkey_str ).strip ().lower ()
        if not h or h in ("none","нет","отключено","[ не назначено ]",""):
            return None

        if h in ("double_ctrl","ctrl+ctrl","ctrl ctrl","2xctrl","двойной ctrl"):
            return ("double_ctrl",None ,None ,None ,None )
        if h in ("double_alt","alt+alt","alt alt","двойной alt"):
            return ("double_alt",None ,None ,None ,None )

        tokens =[k .strip ()for k in re .split (r'[\+\s\-]+',h )if k .strip ()]
        need_ctrl =any (x in ("ctrl","control")for x in tokens )
        need_alt =any (x in ("alt","menu")for x in tokens )
        need_shift =any (x =="shift"for x in tokens )
        need_win =any (x in ("win","windows")for x in tokens )

        vk =None
        for t in tokens :
            if t not in ("ctrl","control","alt","menu","shift","win","windows")and t in VK_MAP :
                vk =VK_MAP [t ]
                break

        if not vk :return None
        return ("combo",need_ctrl ,need_alt ,need_shift ,need_win ,vk )

    def reload_from_config (self ):
        try :
            from data .core .config_manager import config
            ocr_k =config .get_str ("HOTKEYS","OCR","")
            win_k =config .get_str ("HOTKEYS","ToggleWindow","")
            tts_k =config .get_str ("HOTKEYS","TTS","")
        except Exception :
            ocr_k ,win_k ,tts_k ="","",""

        self .ocr_hotkey_parsed =self .parse_hotkey (ocr_k )
        self .toggle_hotkey_parsed =self .parse_hotkey (win_k )
        self .tts_hotkey_parsed =self .parse_hotkey (tts_k )

        has_any =bool (self .ocr_hotkey_parsed or self .toggle_hotkey_parsed or self .tts_hotkey_parsed )
        if has_any and not self .hook_handle :
            self ._attach_hook ()
        elif not has_any and self .hook_handle :
            self .uninstall_hook ()

    def _attach_hook (self ):
        hinst =kernel32 .GetModuleHandleW (None )
        self .hook_handle =user32 .SetWindowsHookExW (WH_KEYBOARD_LL ,self ._hook_ref ,hinst ,0 )

    def install_hook (self ,main_window ):
        self .main_window =main_window
        self .reload_from_config ()

    def uninstall_hook (self ):
        if self .hook_handle :
            user32 .UnhookWindowsHookEx (self .hook_handle )
            self .hook_handle =None

    def _matches_combo (self ,parsed ,vk ,ctrl ,alt ,shift ,win ):
        if not parsed or parsed [0 ]!="combo":return False
        _ ,n_ctrl ,n_alt ,n_shift ,n_win ,target_vk =parsed
        if target_vk !=vk :return False
        if n_ctrl !=ctrl :return False
        if n_alt !=alt :return False
        if n_shift !=shift :return False
        if n_win !=win :return False
        return True

    def _hook_callback (self ,nCode ,wParam ,lParam ):
        if nCode ==0 and wParam in (WM_KEYDOWN ,WM_SYSKEYDOWN ):
            try :
                kbd =ctypes .cast (lParam ,ctypes .POINTER (KBDLLHOOKSTRUCT )).contents
                vk =kbd .vkCode
                now =time .time ()

                ctrl_down =bool ((user32 .GetAsyncKeyState (0x11 )&0x8000 )or (user32 .GetAsyncKeyState (0xA2 )&0x8000 )or (user32 .GetAsyncKeyState (0xA3 )&0x8000 ))
                shift_down =bool ((user32 .GetAsyncKeyState (0x10 )&0x8000 )or (user32 .GetAsyncKeyState (0xA0 )&0x8000 )or (user32 .GetAsyncKeyState (0xA1 )&0x8000 ))
                alt_down =bool ((user32 .GetAsyncKeyState (0x12 )&0x8000 )or (user32 .GetAsyncKeyState (0xA4 )&0x8000 )or (user32 .GetAsyncKeyState (0xA5 )&0x8000 ))
                win_down =bool ((user32 .GetAsyncKeyState (0x5B )&0x8000 )or (user32 .GetAsyncKeyState (0x5C )&0x8000 ))

                if vk in (0x11 ,0xA2 ,0xA3 ):
                    if now -self ._last_ctrl_time <0.35 :
                        if self .ocr_hotkey_parsed and self .ocr_hotkey_parsed [0 ]=="double_ctrl":
                            self ._trigger_ocr ()
                            self ._last_ctrl_time =0
                            return 1
                    self ._last_ctrl_time =now

                elif vk in (0x12 ,0xA4 ,0xA5 ):
                    if now -self ._last_alt_time <0.35 :
                        if self .ocr_hotkey_parsed and self .ocr_hotkey_parsed [0 ]=="double_alt":
                            self ._trigger_ocr ()
                            self ._last_alt_time =0
                            return 1
                    self ._last_alt_time =now

                if self ._matches_combo (self .ocr_hotkey_parsed ,vk ,ctrl_down ,alt_down ,shift_down ,win_down ):
                    self ._trigger_ocr ()
                    return 1

                if self ._matches_combo (self .toggle_hotkey_parsed ,vk ,ctrl_down ,alt_down ,shift_down ,win_down ):
                    self ._trigger_toggle_win ()
                    return 1

                if self ._matches_combo (self .tts_hotkey_parsed ,vk ,ctrl_down ,alt_down ,shift_down ,win_down ):
                    self ._trigger_tts ()
                    return 1

            except Exception :pass

        return user32 .CallNextHookEx (self .hook_handle ,nCode ,wParam ,lParam )

    def _trigger_ocr (self ):
        if self .main_window :
            def _run ():
                try :
                    from data .ocr .ocr_engine import ocr_engine
                    ocr_engine .snip_screen_interactive (self .main_window )
                except Exception :pass
            self .main_window .after (0 ,_run )

    def _trigger_toggle_win (self ):
        if self .main_window :
            def _run ():
                try :
                    if self .main_window .state ()=="withdrawn"or not self .main_window .winfo_viewable ():
                        self .main_window .deiconify ()
                        self .main_window .lift ()
                        self .main_window .focus_force ()
                    else :
                        self .main_window .withdraw ()
                except Exception :pass
            self .main_window .after (0 ,_run )

    def _trigger_tts (self ):
        if self .main_window :
            def _run ():
                try :
                    from data .tts .tts_engine import tts_engine ,grab_selection_from_target_hwnd
                    if tts_engine .is_playing ():
                        tts_engine .stop_speech ()
                        return

                    text =grab_selection_from_target_hwnd (window_tracker .last_user_hwnd )
                    if text :
                        print (f"[TTS]: Озвучивание выделения -> \"{text [:60 ]}...\"")
                        tts_engine .speak_text (text )
                except Exception as e :
                    print (f"[TTS Error]: {e }")
            self .main_window .after (0 ,_run )

hotkey_manager =GlobalHotkeyManager ()
