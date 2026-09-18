# -*- coding: utf-8 -*-
# data/core/config_manager.py

import os, sys
import configparser
def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

class ConfigManager :
    def __init__ (self ,filename ="config.ini"):
        self .base_dir =get_base_dir ()
        self .config_path =os .path .join (self .base_dir ,"data",filename )

        old_root_path =os .path .join (self .base_dir ,filename )
        if os .path .exists (old_root_path )and not os .path .exists (self .config_path ):
            try :
                os .makedirs (os .path .dirname (self .config_path ),exist_ok =True )
                import shutil
                shutil .move (old_root_path ,self .config_path )
            except Exception :
                pass

        self .config =configparser .ConfigParser (interpolation =None )
        self .load ()

    def _get_defaults (self ):
        return {
        "GENERAL":{
        "AutoLaunchQTranslate":"1",
        "ServerPort":"8080",
        "UILanguage":"auto",
        "StartMinimized":"1"
        },
        "WINDOW":{
        "PosX":"-1",
        "PosY":"-1",
        "Width":"820",
        "Height":"640"
        },
        "APPEARANCE":{
        "Theme":"light",
        "FontSize":"normal"
        },
        "BROWSER":{
        "UsePortable":"1",
        "CDPPort":"9222",
        "AutoDismissPopups":"1"
        },
        "SERVICES":{
        "ServiceOrder":"google_ai,deepseek_flash,openai_120b,tencent_hy3,qwen_orca",
        "ActiveService":"google_ai"
        },
        "PRESETS":{
        "google_ai":"default",
        "deepseek_flash":"default",
        "openai_120b":"default",
        "tencent_hy3":"default",
        "qwen_orca":"default"
        },
        "OCR":{
        "ActiveModel":"cyrillic",
        "AutoTranslate":"1"
        },
        "HOTKEYS":{
        "OCR":"",
        "ToggleWindow":"",
        "TTS":""
        },
        "QTRANSLATE":{
        "SummonHotkey":"double_ctrl"
        },
        "TTS":{
        "ActiveProvider":"edge_tts",
        "Voice":"ru-RU-SvetlanaNeural",
        "Speed":"1.0"
        },
        "DICTIONARY":{
        "Enabled":"1",
        "GlossaryFile":"glossary.txt"
        },
        "BATCH":{
        "ChunkSize":"2500",
        "ProtectCode":"1"
        },
        "LOGGING":{
        "ShowConsole":"0",
        "LogToFile":"1",
        "ClearOnStartup":"1",
        "log_api_summary":"1",
        "log_api_payload":"1",
        "log_api_raw_response":"1",
        "log_tools":"1",
        "log_glossary":"1",
        "log_filtering":"1",
        "log_qtranslate":"1",
        "log_browser":"0"
        }
        }

    def load (self ):
        defaults =self ._get_defaults ()
        for section ,values in defaults .items ():
            if not self .config .has_section (section ):
                self .config .add_section (section )
            for k ,v in values .items ():
                if not self .config .has_option (section ,k ):
                    self .config .set (section ,k ,str (v ))

        if os .path .exists (self .config_path ):
            try :
                with open (self .config_path ,"r",encoding ="utf-8")as f :
                    self .config .read_file (f )
            except Exception :
                try :
                    with open (self .config_path ,"r",encoding ="cp1251")as f :
                        self .config .read_file (f )
                except Exception :
                    pass
        else :
            self .save ()

    def save (self ):
        try :
            os .makedirs (os .path .dirname (self .config_path ),exist_ok =True )
            with open (self .config_path ,"w",encoding ="utf-8")as f :
                self .config .write (f )
            return True
        except Exception as e :
            print (f"[ConfigManager Error]: {e }")
            return False

    def get_str (self ,section ,key ,default =""):
        try :
            return self .config .get (section ,key )
        except Exception :
            return default

    def get_int (self ,section ,key ,default =0 ):
        try :
            return self .config .getint (section ,key )
        except Exception :
            return default

    def get_bool (self ,section ,key ,default =False ):
        try :
            val =str (self .config .get (section ,key )).strip ().lower ()
            return val in ("1","true","yes","on")
        except Exception :
            return default

    def get_float (self ,section ,key ,default =1.0 ):
        try :
            return self .config .getfloat (section ,key )
        except Exception :
            return default

    def set_value (self ,section ,key ,value ):
        if not self .config .has_section (section ):
            self .config .add_section (section )
        self .config .set (section ,key ,str (value ).strip ())
        self .save ()

    def get_window_geometry (self ):
        x =self .get_int ("WINDOW","PosX",-1 )
        y =self .get_int ("WINDOW","PosY",-1 )
        w =self .get_int ("WINDOW","Width",820 )
        h =self .get_int ("WINDOW","Height",640 )
        return x ,y ,max (520 ,w ),max (400 ,h )

    def save_window_geometry (self ,x ,y ,width ,height ):
        if width <450 or height <350 or x <-50 or y <-50 :
            return
        if not self .config .has_section ("WINDOW"):
            self .config .add_section ("WINDOW")
        self .config .set ("WINDOW","PosX",str (x ))
        self .config .set ("WINDOW","PosY",str (y ))
        self .config .set ("WINDOW","Width",str (width ))
        self .config .set ("WINDOW","Height",str (height ))
        self .save ()

    def get_service_order (self ):
        raw =self .get_str ("SERVICES","ServiceOrder","google_ai,deepseek_flash,openai_120b,tencent_hy3,qwen_orca")
        return [s .strip ()for s in raw .split (",")if s .strip ()]

    def save_service_order (self ,order_list ):
        self .set_value ("SERVICES","ServiceOrder",",".join (order_list ))

    def get_active_preset (self ,service_id ):
        return self .get_str ("PRESETS",service_id ,"default")

    def set_active_preset (self ,service_id ,preset_name ):
        self .set_value ("PRESETS",service_id ,preset_name )

config =ConfigManager ()
