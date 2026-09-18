# -*- coding: utf-8 -*-
# data/core/service_generator.py

import os, re, shutil, sys, time
import importlib
from data.core.api_config import api_config
from data.core.launcher import restart_qtranslate
from data.core.logger import logger
from data.core.templates.common_js import JS_SERVICE_TEMPLATE
from data.core.templates.unified_engine import UNIFIED_PYTHON_TEMPLATE
__all__ =[
"slugify",
"get_next_available_qt_id",
"get_known_providers",
"get_provider_spec",
"create_unified_service",
"delete_service_completely",
"test_ping_service",
]

def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

def slugify (text ):
    text =re .sub (r'[^a-zA-Z0-9_]','_',text .lower ()).strip ('_')
    return re .sub (r'_+','_',text )

def get_next_available_qt_id ():
    base_dir =get_base_dir ()
    used_ids ={675 ,681 ,685 ,686 ,694 ,696 ,698 ,700 ,701 ,702 ,703 ,704 ,705 ,706 ,707 ,708 ,709 ,710 ,103 ,111 ,11 ,118 ,119 }

    services_dir =os .path .join (base_dir ,"Services")
    if os .path .exists (services_dir ):
        for root ,_ ,files in os .walk (services_dir ):
            for file in files :
                if file .lower ()=="service.js":
                    try :
                        with open (os .path .join (root ,file ),"r",encoding ="utf-8")as f :
                            content =f .read ()
                            m =re .search (r'SERVICE_ID\s*=\s*(\d+)',content )
                            if m :
                                used_ids .add (int (m .group (1 )))
                    except Exception :
                        pass

    candidate =711
    while candidate in used_ids :
        candidate +=1
    return candidate

def get_known_providers ():
    base_dir =get_base_dir ()
    tpl_dir =os .path .join (base_dir ,"data","core","templates")
    providers =[]

    if os .path .exists (tpl_dir ):
        ignore_files ={"common_js.py","unified_engine.py","__init__.py"}
        for item in sorted (os .listdir (tpl_dir )):
            if item .endswith (".py")and item not in ignore_files :
                mod_name =item [:-3 ]
                try :
                    mod =importlib .import_module (f"data.core.templates.{mod_name }")
                    p_key =getattr (mod ,"PROVIDER_KEY",mod_name )
                    p_name =getattr (mod ,"PROVIDER_NAME",mod_name .capitalize ())
                    providers .append ((p_key ,p_name ))
                except Exception as e :
                    logger .system (f"Генератор: сбой импорта шаблона '{item }': {e }")

    has_custom =any (k =="custom"for k ,_ in providers )
    if not has_custom :
        providers .append (("custom","Пользовательский шаблон (С нуля...)"))

    return providers

def get_provider_spec (provider_key ):
    if provider_key =="custom":
        return {
        "name":"Пользовательский шаблон (С нуля...)",
        "endpoint":"https://api.example.com/v1/chat/completions",
        "default_model":"custom-model",
        "auth_header_type":"Bearer",
        "thinking_policy":"none",
        "response_path":"choices.0.message.content",
        "connection_mode":"direct",
        "proxy":"127.0.0.1:10808",
        "extra_headers":{}
        }

    try :
        mod =importlib .import_module (f"data.core.templates.{provider_key }")
        return {
        "name":getattr (mod ,"PROVIDER_NAME",provider_key .capitalize ()),
        "endpoint":getattr (mod ,"DEFAULT_ENDPOINT","https://api.example.com/v1/chat/completions"),
        "default_model":getattr (mod ,"DEFAULT_MODEL","model-id"),
        "auth_header_type":getattr (mod ,"AUTH_HEADER_TYPE","Bearer"),
        "thinking_policy":getattr (mod ,"THINKING_POLICY","none"),
        "response_path":getattr (mod ,"RESPONSE_PATH","choices.0.message.content"),
        "connection_mode":getattr (mod ,"CONNECTION_MODE","direct"),
        "proxy":getattr (mod ,"DEFAULT_PROXY","127.0.0.1:10808"),
        "extra_headers":getattr (mod ,"EXTRA_HEADERS",{})
        }
    except Exception as e :
        logger .system (f"Генератор: сбой чтения параметров шаблона '{provider_key }': {e }")
        return get_provider_spec ("custom")

def create_unified_service (
provider_key ,service_name ,service_slug ="",model_id ="",
endpoint ="",qt_id =None ,auth_header_type ="Bearer",
thinking_policy ="none",response_path ="choices.0.message.content",
extra_headers_json ="{}",api_key ="",connection_mode ="direct",
proxy ="",doh_preset ="Comss.one (SmartDNS / РФ обход)"
):
    base_dir =get_base_dir ()
    slug =slugify (service_slug or service_name )
    if not slug :
        slug ="custom_service"

    target_qt_id =int (qt_id )if qt_id else get_next_available_qt_id ()

    py_code =(
    UNIFIED_PYTHON_TEMPLATE
    .replace ("{SERVICE_NAME}",service_name )
    .replace ("{SERVICE_ID_SLUG}",slug )
    .replace ("{MODEL_ID}",model_id )
    .replace ("{ENDPOINT}",endpoint )
    .replace ("{PROVIDER_KEY}",provider_key )
    .replace ("{AUTH_HEADER_TYPE}",auth_header_type )
    .replace ("{THINKING_POLICY}",thinking_policy )
    .replace ("{RESPONSE_PATH}",response_path )
    .replace ("{EXTRA_HEADERS_JSON}",extra_headers_json )
    )

    py_dir =os .path .join (base_dir ,"data","services",slug )
    os .makedirs (py_dir ,exist_ok =True )
    py_file =os .path .join (py_dir ,"service.py")
    with open (py_file ,"w",encoding ="utf-8")as f :
        f .write (py_code )

    js_folder_name =re .sub (r'[^a-zA-Z0-9_\- ]','',service_name ).strip ()or slug
    js_dir =os .path .join (base_dir ,"Services",js_folder_name )
    os .makedirs (js_dir ,exist_ok =True )
    js_file =os .path .join (js_dir ,"service.js")

    js_code =(
    JS_SERVICE_TEMPLATE
    .replace ("{SERVICE_NAME}",service_name )
    .replace ("{SERVICE_ID_SLUG}",slug )
    .replace ("{QT_ID}",str (target_qt_id ))
    )
    with open (js_file ,"w",encoding ="utf-8")as f :
        f .write (js_code )

    if api_key :
        api_config .set_provider_val (provider_key ,"api_key",api_key )
    if connection_mode :
        api_config .set_provider_val (provider_key ,"connection_mode",connection_mode )
    if proxy :
        api_config .set_provider_val (provider_key ,"proxy",proxy )
    if doh_preset :
        api_config .set_provider_val (provider_key ,"doh_preset",doh_preset )

    api_config .set_val (slug ,"provider",provider_key )
    api_config .set_val (slug ,"model",model_id )
    api_config .set_val (slug ,"endpoint",endpoint )
    api_config .set_val (slug ,"temperature","0.2")
    api_config .set_val (slug ,"top_p","0.3")
    api_config .set_val (slug ,"max_tokens","4096")
    api_config .set_val (slug ,"enable_thinking","0")
    api_config .set_val (slug ,"enable_glossary","1")

    preset_dir =os .path .join (base_dir ,"data","presets",slug )
    os .makedirs (preset_dir ,exist_ok =True )
    def_preset =os .path .join (preset_dir ,"default.txt")
    if not os .path .exists (def_preset ):
        with open (def_preset ,"w",encoding ="utf-8")as f :
            f .write (
            "Сделай профессиональный перевод на {TARGET_LANG} с точной передачей стиля оригинала.\n"
            "ПРАВИЛА:\n"
            "1. Стиль и мимикрия: точно воспроизводи стиль, регистр и тональность источника.\n"
            "2. Терминология: устоявшиеся официальные термины пиши на целевом языке, уникальные бренды — в оригинале."
            )

    from data .services .base_service import load_all_services
    load_all_services ()

    restart_qtranslate ()

    logger .system (f"Генератор: создан единый сервис '{service_name }' ({slug }) [QT_ID: {target_qt_id }]")
    return True ,slug ,py_file ,js_file

def test_ping_service (service_slug ,text =None ,src ="en",trg ="ru"):
    from data .services .base_service import LOADED_SERVICES

    srv =LOADED_SERVICES .get (service_slug )
    if not srv :
        return False ,f"Сервис '{service_slug }' не найден среди загруженных плагинов.",0.0

    if not text :
        text ="Connection test:\nVerifying remote model response, API status and network latency."

    t0 =time .time ()
    try :
        res =srv .translate (text ,src_lang =src ,trg_lang =trg )
        elapsed =round (time .time ()-t0 ,2 )
        if res and not str (res ).startswith ("Ошибка")and not str (res ).startswith ("[")and not "HTTP "in str (res ):
            return True ,str (res ),elapsed
        return False ,str (res ),elapsed
    except Exception as e :
        elapsed =round (time .time ()-t0 ,2 )
        return False ,f"Исключение при вызове: {e }",elapsed

def delete_service_completely (service_id ,service_name ):
    base_dir =get_base_dir ()
    slug =slugify (service_id )

    py_dir =os .path .join (base_dir ,"data","services",slug )
    if os .path .exists (py_dir ):
        shutil .rmtree (py_dir ,ignore_errors =True )

    js_candidates =[
    os .path .join (base_dir ,"Services",service_name ),
    os .path .join (base_dir ,"Services",slug ),
    os .path .join (base_dir ,"Services",slug .capitalize ())
    ]
    for p in js_candidates :
        if os .path .exists (p ):
            shutil .rmtree (p ,ignore_errors =True )

    preset_dir =os .path .join (base_dir ,"data","presets",slug )
    if os .path .exists (preset_dir ):
        shutil .rmtree (preset_dir ,ignore_errors =True )

    if api_config .models .has_section (slug ):
        api_config .models .remove_section (slug )
        api_config .save_models ()

    from data .services .base_service import LOADED_SERVICES ,load_all_services
    if slug in LOADED_SERVICES :
        del LOADED_SERVICES [slug ]
    load_all_services ()

    restart_qtranslate ()
    logger .system (f"Генератор: сервис '{service_name }' ({slug }) полностью удален")
    return True
