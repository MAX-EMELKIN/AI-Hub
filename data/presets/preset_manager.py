# -*- coding: utf-8 -*-
# data/presets/preset_manager.py
import os
import sys

def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

DEFAULT_PRESETS_DATA ={
"default":(
"Text Text Text Text {TARGET_LANG} Text Text Text Text Text.\n"
"Text:\n"
"1. Text Text Text: Text Text Text, Text Text Text Text.\n"
"2. Text: Text Text Text Text Text Text Text, Text Text Text Text — Text Text (Text Text Text Text)."
),
"games":(
"Text — Text Text Text. Text Text Text Text Text Text {TARGET_LANG}.\n"
"Text:\n"
"1. Text Text: Text Text Text Text. Text Text Text Text Text Text, Text, Text Text Text — Text Text Text Text Text Text Text Text Text.\n"
"2. Text Text: Text Text Text Text Text, Text Text Text.\n"
"3. Text Text Text Text: Text Text Text Text Text Text."
),
"academic":(
"Text Text Text/Text Text Text {TARGET_LANG}.\n"
"Text:\n"
"1. Text Text: Text Text Text Text. Text Text, Text Text Text.\n"
"2. Text Text: Text Text Text Text Text Text Text.\n"
"3. Text Text: Text Text Text-Text Text Text Text Text."
),
"literary":(
"Text — Text Text Text Text Text. Text Text Text Text Text {TARGET_LANG}.\n"
"Text:\n"
"1. Text: Text Text Text Text, Text Text Text Text Text Text.\n"
"2. Text: Text Text Text, Text Text Text Text.\n"
"3. Text Text Text Text Text — Text Text Text Text Text Text."
),
"code":(
"Text Text Text Text Text Text IT-Text Text {TARGET_LANG}.\n"
"Text:\n"
"1. Text Text Text Text Text, Text Text, Text (camelCase, snake_case), Text Text Text Text Text Text.\n"
"2. Text Text Text, Text, Text Text Text Text Text.\n"
"3. Text Text Text Text Text Text."
)
}

class PresetManager :

    def __init__ (self ):
        self .base_dir =get_base_dir ()
        self .presets_root =os .path .join (self .base_dir ,"data","presets")
        os .makedirs (self .presets_root ,exist_ok =True )

    def _get_service_dir (self ,service_id ):
        s_id =str (service_id ).lower ().strip ().replace ("/","")
        s_dir =os .path .join (self .presets_root ,s_id )
        os .makedirs (s_dir ,exist_ok =True )
        return s_dir

    def ensure_service_presets (self ,service_id ):
        s_dir =self ._get_service_dir (service_id )
        for name ,text in DEFAULT_PRESETS_DATA .items ():
            f_path =os .path .join (s_dir ,f"{name }.txt")
            if not os .path .exists (f_path ):
                try :
                    with open (f_path ,"w",encoding ="utf-8")as f :
                        f .write (text .strip ())
                except Exception :pass

    def get_presets_for_service (self ,service_id ):
        self .ensure_service_presets (service_id )
        s_dir =self ._get_service_dir (service_id )

        presets =set ()
        for item in os .listdir (s_dir ):
            if item .lower ().endswith (".txt"):
                presets .add (item [:-4 ])

        for base in DEFAULT_PRESETS_DATA .keys ():
            presets .add (base )

        sorted_list =sorted ([p for p in presets if p !="default"])
        return ["default"]+sorted_list

    def get_preset_text (self ,service_id ,preset_name ):
        s_dir =self ._get_service_dir (service_id )
        p_path =os .path .join (s_dir ,f"{preset_name }.txt")

        if os .path .exists (p_path ):
            try :
                with open (p_path ,"r",encoding ="utf-8")as f :
                    content =f .read ().strip ()
                    if content :return content
            except Exception :pass

        default_content =DEFAULT_PRESETS_DATA .get (preset_name ,DEFAULT_PRESETS_DATA ["default"])
        try :
            with open (p_path ,"w",encoding ="utf-8")as f :
                f .write (default_content .strip ())
        except Exception :pass
        return default_content

    def save_preset (self ,service_id ,preset_name ,content ):
        s_dir =self ._get_service_dir (service_id )
        p_path =os .path .join (s_dir ,f"{preset_name }.txt")
        try :
            with open (p_path ,"w",encoding ="utf-8")as f :
                f .write (content .strip ())
            return True
        except Exception as e :
            print (f"[PresetManager Error]: Text Text Text Text '{preset_name }' Text '{service_id }': {e }")
            return False

    def delete_preset (self ,service_id ,preset_name ):
        if preset_name =="default":
            return False

        s_dir =self ._get_service_dir (service_id )
        p_path =os .path .join (s_dir ,f"{preset_name }.txt")
        if os .path .exists (p_path ):
            try :
                os .remove (p_path )
                return True
            except Exception :pass
        return False

    def _ensure_default_presets (self ):
        for s_id in ["google_ai","deepseek_flash","openai_120b","tencent_hy3","qwen_orca"]:
            self .ensure_service_presets (s_id )

preset_manager =PresetManager ()
