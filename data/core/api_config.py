# -*- coding: utf-8 -*-
# data/core/api_config.py

import os, sys
import configparser
from data.core.logger import logger
from data.core.web_search import DEFAULT_SEARCH_PROMPT
def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

PROVIDER_KEYS ={
"api_key","account_id","api_token",
"connection_mode","proxy","doh_preset","doh_custom_url"
}

class APIConfigManager :
    def __init__ (self ):
        self .base_dir =get_base_dir ()
        self .data_dir =os .path .join (self .base_dir ,"data")
        self .providers_path =os .path .join (self .data_dir ,"providers.ini")
        self .models_path =os .path .join (self .data_dir ,"models.ini")
        self .old_config_path =os .path .join (self .data_dir ,"api_keys.ini")

        self .providers =configparser .ConfigParser (interpolation =None )
        self .models =configparser .ConfigParser (interpolation =None )

        self ._migrate_if_needed ()
        self .load ()

    def _guess_provider (self ,sec ,old_conf ):
        endpoint =old_conf .get (sec ,"endpoint",fallback ="").lower ()
        if "dashscope"in endpoint :return "dashscope"
        if "deepseek"in endpoint :return "deepseek"
        if "moonshot"in endpoint :return "moonshot"
        if "openrouter"in endpoint :return "openrouter"
        if "boltch"in endpoint :return "boltch"
        if "orcarouter"in endpoint :return "orcarouter"
        if "cloudflare"in endpoint :return "cloudflare"
        if "generativelanguage"in endpoint or sec =="gemini_family":return "gemini"
        return "custom"

    def _migrate_if_needed (self ):
        if os .path .exists (self .providers_path )and os .path .exists (self .models_path ):
            return

        old_path =self .old_config_path if os .path .exists (self .old_config_path )else os .path .join (self .base_dir ,"api_keys.ini")
        if os .path .exists (old_path ):
            old_conf =configparser .ConfigParser (interpolation =None )
            try :
                old_conf .read (old_path ,encoding ="utf-8")
            except :
                old_conf .read (old_path ,encoding ="cp1251")

            for sec in old_conf .sections ():
                provider =self ._guess_provider (sec ,old_conf )

                if not self .models .has_section (sec ):
                    self .models .add_section (sec )
                self .models .set (sec ,"provider",provider )

                if not self .providers .has_section (provider ):
                    self .providers .add_section (provider )

                for k ,v in old_conf .items (sec ):
                    val_str =str (v ).strip ()
                    if k in PROVIDER_KEYS :

                        if not self .providers .has_option (provider ,k )or (val_str and not self .providers .get (provider ,k )):
                            self .providers .set (provider ,k ,val_str )
                    else :
                        self .models .set (sec ,k ,val_str )

            self .save_providers ()
            self .save_models ()
            try :
                os .rename (old_path ,old_path +".bak")
            except Exception :
                pass
            logger .system ("Миграция api_keys.ini в providers.ini и models.ini успешно завершена.")

    def load (self ):
        if os .path .exists (self .providers_path ):
            try :
                self .providers .read (self .providers_path ,encoding ="utf-8")
            except Exception :
                self .providers .read (self .providers_path ,encoding ="cp1251")

        if os .path .exists (self .models_path ):
            try :
                self .models .read (self .models_path ,encoding ="utf-8")
            except Exception :
                self .models .read (self .models_path ,encoding ="cp1251")

    def save_providers (self ):
        os .makedirs (self .data_dir ,exist_ok =True )
        with open (self .providers_path ,"w",encoding ="utf-8")as f :
            self .providers .write (f )

    def save_models (self ):
        os .makedirs (self .data_dir ,exist_ok =True )
        with open (self .models_path ,"w",encoding ="utf-8")as f :
            self .models .write (f )

    def get_provider_val (self ,provider_id ,key ,default =""):
        prov =provider_id .lower ().strip ()
        if self .providers .has_section (prov )and self .providers .has_option (prov ,key ):
            val =self .providers .get (prov ,key )
            if val is not None and str (val ).strip ():
                return val
        return default

    def set_provider_val (self ,provider_id ,key ,value ):
        prov =provider_id .lower ().strip ()
        if not self .providers .has_section (prov ):
            self .providers .add_section (prov )
        self .providers .set (prov ,key ,str (value ).strip ())
        self .save_providers ()

    def get_val (self ,service_id ,key ,default =""):
        sec =service_id .lower ().strip ()

        if key in PROVIDER_KEYS :
            if self .models .has_section (sec )and self .models .has_option (sec ,"provider"):
                provider =self .models .get (sec ,"provider").lower ().strip ()
            else :
                provider ="custom"
            return self .get_provider_val (provider ,key ,default )

        try :
            if self .models .has_section (sec )and self .models .has_option (sec ,key ):
                val =self .models .get (sec ,key )
                if val is not None and str (val ).strip ():
                    return val
        except Exception :
            pass

        if key =="search_prompt":
            return DEFAULT_SEARCH_PROMPT

        return default

    def set_val (self ,service_id ,key ,value ):
        sec =service_id .lower ().strip ()

        if key in PROVIDER_KEYS :
            if self .models .has_section (sec )and self .models .has_option (sec ,"provider"):
                provider =self .models .get (sec ,"provider").lower ().strip ()
            else :
                provider ="custom"
                if not self .models .has_section (sec ):
                    self .models .add_section (sec )
                self .models .set (sec ,"provider",provider )
            self .set_provider_val (provider ,key ,value )
        else :
            if not self .models .has_section (sec ):
                self .models .add_section (sec )
            self .models .set (sec ,key ,str (value ).strip ())
            self .save_models ()

api_config =APIConfigManager ()
