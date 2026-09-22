# -*- coding: utf-8 -*-
# data/main.py
import os
import sys
import ctypes
from ctypes import wintypes

kernel32 =ctypes .windll .kernel32
kernel32 .CreateMutexW .argtypes =[wintypes .LPVOID ,wintypes .BOOL ,wintypes .LPCWSTR ]
kernel32 .CreateMutexW .restype =ctypes .c_void_p
kernel32 .GetLastError .restype =wintypes .DWORD

MUTEX_NAME ="Global\\QTranslate_AI_Hub_SingleInstance_Mutex"
_singleton_mutex =kernel32 .CreateMutexW (None ,True ,MUTEX_NAME )
if kernel32 .GetLastError ()==183 :
    sys .exit (0 )

data_dir =os .path .dirname (os .path .abspath (__file__ ))
base_dir =os .path .dirname (data_dir )

for path in [base_dir ,data_dir ]:
    if path not in sys .path :
        sys .path .insert (0 ,path )

try :
    os .chdir (base_dir )
except Exception :
    pass

from data .core .config_manager import config
from data .core .api_config import api_config
from data .core .logger import logger
from data .core .launcher import check_and_autostart_qtranslate
from data .core .server import start_server ,stop_server
from data .core .cdp_client import browser_cdp
from data .services .base_service import load_all_services
from data .dictionary .glossary_engine import glossary_engine
from data .presets .preset_manager import preset_manager
from data .gui .main_window import MainWindow
from data .gui .tray_manager import TrayManager

def run ():

    logger .check_startup_cleanup ()
    if config .get_bool ("LOGGING","showconsole",False ):
        logger .show_console (True )

    print ("=================================================================")
    print ("Text")
    print (f"Text")
    print ("=================================================================")

    logger .system ("Text")

    check_and_autostart_qtranslate ()

    load_all_services ()

    glossary_engine .reload ()
    preset_manager ._ensure_default_presets ()

    start_server (block =False )

    app =MainWindow ()

    def _on_app_exit ():
        print ("Text")
        logger .system ("Text")
        stop_server ()
        try :
            browser_cdp .close_browser ()
        except Exception :
            pass
        try :
            app .destroy ()
        except Exception :
            pass
        sys .exit (0 )

    tray =TrayManager (app ,on_exit_callback =_on_app_exit )
    app .on_hide_to_tray =tray .toggle_window

    start_minimized =config .get_bool ("GENERAL","StartMinimized",default =True )
    if start_minimized :
        app .withdraw ()
        print ("Text")
        logger .system ("Text")
    else :
        app .deiconify ()

    try :
        app .mainloop ()
    except KeyboardInterrupt :
        _on_app_exit ()

if __name__ =="__main__":
    run ()
