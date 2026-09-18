# -*- coding: utf-8 -*-
# data/services/base_service.py
import os
import sys
import re
import time
import json
import importlib
import urllib .parse
import urllib .request
from data .core .api_config import api_config
from data .presets .preset_manager import preset_manager
from data .core .logger import logger

def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

LANG_NAMES ={
"ru":"русский язык","en":"английский язык","de":"немецкий язык","fr":"французский язык",
"es":"испанский язык","it":"итальянский язык","zh":"китайский язык","zh-cn":"китайский язык (упрощенный)",
"zh-tw":"традиционный китайский язык","ja":"японский язык","ko":"корейский язык",
"pt":"португальский язык","pl":"польский язык","uk":"украинский язык","be":"белорусский язык",
"tr":"турецкий язык","ar":"арабский язык","he":"иврит","iw":"иврит","hi":"хинди","nl":"нидерландский язык",
"sv":"шведский язык","no":"норвежский язык","fi":"финский язык","da":"датский язык","cs":"чешский язык",
"el":"греческий язык","ro":"румынский язык","hu":"венгерский язык","bg":"болгарский язык",
"sr":"сербский язык","sk":"словацкий язык","sl":"словенский язык","hr":"хорватский язык",
"lt":"литовский язык","lv":"латышский язык","et":"эстонский язык","vi":"вьетнамский язык",
"th":"тайский язык","id":"индонезийский язык","ms":"малайский язык","fa":"персидский язык",
"ka":"грузинский язык","hy":"армянский язык","az":"азербайджанский язык","kk":"казахский язык",
"uz":"узбекский язык","tg":"таджикский язык","la":"латынь","eo":"эсперанто"
}

USER_AGENT ="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

class BaseService :
    def __init__ (self ,service_id ,name ,route_name ,icon_name ="Service.png"):
        self .service_id =service_id
        self .name =name
        self .route_name =route_name
        self .icon_name =icon_name
        self .base_dir =get_base_dir ()
        self .end_marker ="###END###"
        self .supports_hyperparameters =True

    def get_config_fields (self ):
        return [
        {"key":"api_key","label":"API Ключ:","required":True },
        {"key":"model","label":"Модель:","required":True },
        {"key":"endpoint","label":"Эндпоинт URL:","required":True }
        ]

    def get_config_val (self ,key ,default =""):
        return api_config .get_val (self .service_id ,key ,default )

    def set_config_val (self ,key ,value ):
        api_config .set_val (self .service_id ,key ,value )

    def is_ready (self ):
        fields =self .get_config_fields ()
        missing =[]
        for f in fields :
            if f .get ("required"):
                val =self .get_config_val (f ["key"])
                if not val or not str (val ).strip ():
                    missing .append (f ["label"].replace (":",""))

        if missing :
            return False ,"Заполните данные в параметрах сервиса ("+", ".join (missing )+")"
        return True ,"Сервис настроен и готов к работе"

    def get_icon_path (self ):
        service_dir =os .path .join (self .base_dir ,"data","services",self .service_id )
        candidates =[
        "Service.png","service.png","Icon.png","icon.png",
        "Service.ico","service.ico","Icon.ico","icon.ico"
        ]
        if os .path .exists (service_dir ):
            for name in candidates :
                p =os .path .join (service_dir ,name )
                if os .path .exists (p ):
                    return os .path .abspath (p )
        return None

    def get_target_lang_name (self ,lang_code ):
        return LANG_NAMES .get (str (lang_code ).lower (),f"{lang_code } язык")

    def load_preset_text (self ,preset_name =None ):
        if not preset_name :
            try :
                from data .core .config_manager import config
                preset_name =config .get_active_preset (self .service_id )
            except Exception :
                preset_name ="default"
        return preset_manager .get_preset_text (self .service_id ,preset_name )

    def prepare_text_and_prompt (self ,source_text ,src_lang ="auto",trg_lang ="ru",preset =None ):
        target_name =self .get_target_lang_name (trg_lang )
        preset_raw =self .load_preset_text (preset_name =preset )

        prompt_rules =re .sub (
        r'\{TARGET_LANG\}|\{target_lang\}|\{ЯЗЫК\}|\{язык\}',
        target_name ,
        preset_raw ,
        flags =re .IGNORECASE
        )
        if trg_lang .lower ()!="ru":
            prompt_rules =re .sub (r'на русский язык',f'на {target_name }',prompt_rules ,flags =re .IGNORECASE )
            prompt_rules =re .sub (r'на русский',f'на {target_name }',prompt_rules ,flags =re .IGNORECASE )

        enable_glossary =self .get_config_val ("enable_glossary","1")in ("1","true","yes")
        glossary_rule =""
        annotated_text =source_text

        if enable_glossary :
            try :
                from data .dictionary .glossary_engine import glossary_engine
                annotated_text ,glossary_rule =glossary_engine .inject_hints (source_text )
                if glossary_rule :
                    matches =re .findall (r'(\b[^\s\[]+)\s+\[\[__GLOSS:([^\]]+)__\]\]',annotated_text )
                    if matches :
                        logger .glossary_match (self .name ,matches )
            except Exception :
                pass

        src_info =f" с языка '{src_lang }'"if (src_lang and src_lang !="auto")else ""

        system_prompt =(
        f"{prompt_rules }\n\n"
        f"ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:\n"
        f"1. Переведи входной текст{src_info } на {target_name } в точном соответствии со стилем.\n"
        f"2. Выводи СТРОГО чистый готовый перевод БЕЗ вводных слов, пояснений и кавычек.\n"
        f"3. СТРОГО СОХРАНЯЙ все переносы строк, структуру списков и абзацев оригинала! "
        f"Категорически запрещено объединять отдельные строки и пункты в один сплошной абзац.\n"
        f"4. Сохраняй все теги разметки, переменные и технические маркеры без изменений."
        )

        if glossary_rule :
            system_prompt +=f"\n\n{glossary_rule }"

        clean_text =annotated_text .replace ('\r\n','\n').replace ('\r','\n')
        return clean_text ,system_prompt

    def query_llm_raw (self ,system_prompt ,user_content ,max_tokens =1500 ,temperature =0.2 ):
        endpoint =self .get_config_val ("endpoint","")
        model =self .get_config_val ("model","")
        t0 =time .time ()

        if "cloudflare.com"in endpoint :
            account_id =self .get_config_val ("account_id")
            api_token =self .get_config_val ("api_token")
            url =endpoint .replace ("{account_id}",account_id ).replace ("{model}",model )

            payload ={
            "messages":[
            {"role":"system","content":system_prompt },
            {"role":"user","content":user_content }
            ],
            "reasoning_effort":"low",
            "max_tokens":max_tokens ,
            "temperature":temperature
            }
            headers ={
            "Content-Type":"application/json",
            "Authorization":f"Bearer {api_token }",
            "User-Agent":USER_AGENT
            }

            logger .api_payload (self .name ,model ,url ,headers ,payload )

            try :
                req =urllib .request .Request (url ,data =json .dumps (payload ).encode ("utf-8"),headers =headers )
                with urllib .request .urlopen (req ,timeout =25.0 )as resp :
                    raw_bytes =resp .read ()
                    elapsed =time .time ()-t0
                    raw_str =raw_bytes .decode ("utf-8")
                    data =json .loads (raw_str )

                    logger .api_raw_response (self .name ,resp .status ,elapsed ,raw_str )
                    logger .api_summary (self .name ,model ,elapsed ,resp .status )

                res =""
                if data .get ("result"):
                    res =data ["result"].get ("response")or data ["result"].get ("output_text")or ""
                return str (res )
            except Exception as e :
                logger .api_summary (self .name ,model ,time .time ()-t0 ,0 ,note =f"Ошибка: {e }")
                return ""

        else :
            api_key =self .get_config_val ("api_key")
            payload ={
            "model":model ,
            "messages":[
            {"role":"system","content":system_prompt },
            {"role":"user","content":user_content }
            ],
            "max_tokens":max_tokens ,
            "temperature":temperature ,
            "include_reasoning":False
            }

            if "glm"in model .lower ():
                payload ["reasoning_effort"]="low"

            headers ={
            "Content-Type":"application/json",
            "Authorization":f"Bearer {api_key }",
            "User-Agent":USER_AGENT
            }

            logger .api_payload (self .name ,model ,endpoint ,headers ,payload )

            try :
                req =urllib .request .Request (endpoint ,data =json .dumps (payload ).encode ("utf-8"),headers =headers )
                with urllib .request .urlopen (req ,timeout =30.0 )as resp :
                    raw_bytes =resp .read ()
                    elapsed =time .time ()-t0
                    raw_str =raw_bytes .decode ("utf-8")
                    data =json .loads (raw_str )

                    logger .api_raw_response (self .name ,resp .status ,elapsed ,raw_str )
                    logger .api_summary (self .name ,model ,elapsed ,resp .status )

                res =""
                if data .get ("choices")and len (data ["choices"])>0 :
                    msg =data ["choices"][0 ].get ("message",{})
                    if isinstance (msg ,dict ):
                        res =msg .get ("content")or msg .get ("reasoning")or msg .get ("reasoning_content")or ""

                res =re .sub (r'<think>[\s\S]*?</think>','',str (res ),flags =re .IGNORECASE ).strip ()
                return str (res )
            except Exception as e :
                logger .api_summary (self .name ,model ,time .time ()-t0 ,0 ,note =f"Ошибка: {e }")
                return ""

    def build_prompt_query (self ,source_text ,src_lang ="auto",trg_lang ="ru",preset =None ):
        clean_text ,system_prompt =self .prepare_text_and_prompt (source_text ,src_lang ,trg_lang ,preset )

        query =(
        f"{system_prompt }\n\n"
        f"5. В самом конце текста находится маркер {self .end_marker }. ОБЯЗАТЕЛЬНО выведи {self .end_marker } в самом конце перевода!\n"
        f"6. Вывод — строго только сам перевод:\n"
        f'"""\n{clean_text } {self .end_marker }\n"""'
        )
        return query

    def fetch_fast_word (self ,text_input ,src ="auto",trg ="ru"):
        try :
            url ="https://translate.googleapis.com/translate_a/single?"+urllib .parse .urlencode ({
            "client":"gtx","sl":src ,"tl":trg ,"dt":"t","q":text_input
            })
            req =urllib .request .Request (url ,headers ={"User-Agent":USER_AGENT ,"Accept":"*/*"})
            with urllib .request .urlopen (req ,timeout =2.5 )as resp :
                data =json .loads (resp .read ().decode ("utf-8"))
                if data and data [0 ]:
                    translated ="".join ([p [0 ]for p in data [0 ]if p and p [0 ]]).strip ()
                    if len (text_input .strip ().split ())<=1 and len (text_input .strip ())<10 :
                        translated =re .split (r'[,;/]',translated )[0 ].strip ()
                    return translated
        except Exception :
            pass
        return ""

    def clean_response (self ,raw_text ,ui_junk_list =None ):
        if not raw_text :
            return ""
        cleaned =raw_text .strip ()

        cleaned =re .sub (r'\[\[__GLOSS:[^\]]+__\]\]','',cleaned )
        cleaned =re .sub (r'\[\s*\[\s*__GLOSS:[^\]]+__\s*\]\s*\]','',cleaned )

        for marker in [self .end_marker ,"### END ###","###END","[[END]]","[END]"]:
            if marker in cleaned :
                cleaned =cleaned .split (marker )[0 ].strip ()
                break

        if '"""'in cleaned :
            parts =[p .strip ()for p in cleaned .split ('"""')if p .strip ()]
            if parts :
                cleaned =parts [-1 ]

        cleaned =cleaned .replace ('\r\n','\n').replace ('\r','\n')
        cleaned =re .sub (r'<br\s*/?>\s*\n?','\n',cleaned ,flags =re .IGNORECASE )
        cleaned =re .sub (r'<br\s*/?>','\n',cleaned ,flags =re .IGNORECASE )

        if ui_junk_list :
            lines =cleaned .split ("\n")
            pure =[]
            for line in lines :
                l =line .strip ()
                if not l :
                    pure .append ("")
                    continue
                if any (junk .lower ()==l .lower ()or l .lower ().startswith (junk .lower ())for junk in ui_junk_list ):
                    continue
                if l .lower ().startswith ("перевод на")or l .lower ().startswith ("сделай")or l .startswith ('"""')or l .endswith ('"""'):
                    continue
                pure .append (line )
            cleaned ="\n".join (pure ).strip ()

        cleaned =re .sub (r'^(?:AI Overview|ИИ-ответ|Обзор от ИИ|Перевод:?|Ответ:?|Translation:?)\s*','',cleaned ,flags =re .IGNORECASE ).strip ()

        cleaned =re .sub (r'^(?:"""|\"|\'|«|“|”|\s|\n)+','',cleaned )
        cleaned =re .sub (r'(?:"""|\"|\'|»|”|\s|\n)+$','',cleaned )
        cleaned =re .sub (r'\n{3,}','\n\n',cleaned ).strip ()

        if raw_text .strip ()!=cleaned :
            logger .text_filtering (self .name ,"Очистка текста ответа",raw_text ,cleaned )

        return cleaned

    def translate (self ,text ,src_lang ="auto",trg_lang ="ru",preset =None ):
        raise NotImplementedError ()

LOADED_SERVICES ={}

def load_all_services ():
    base_dir =get_base_dir ()
    services_root =os .path .join (base_dir ,"data","services")
    if not os .path .exists (services_root ):
        return

    try :
        from data .core .server import register_service_route
    except Exception :
        register_service_route =None

    for item in os .listdir (services_root ):
        item_path =os .path .join (services_root ,item )
        if item .startswith ("__")or item .startswith ("."):
            continue

        service_file =os .path .join (item_path ,"service.py")
        if os .path .isdir (item_path )and os .path .exists (service_file ):
            try :
                module_name =f"data.services.{item }.service"
                mod =importlib .import_module (module_name )

                for attr_name in dir (mod ):
                    attr =getattr (mod ,attr_name )
                    if hasattr (attr ,"service_id")and hasattr (attr ,"translate")and hasattr (attr ,"route_name"):
                        LOADED_SERVICES [attr .service_id ]=attr
                        if register_service_route :
                            register_service_route (attr .service_id ,attr .translate )
                            register_service_route (attr .route_name ,attr .translate )
                        print (f"[Plugin System]: [OK] Загружен сервис: {attr .name } (ID: {attr .service_id })")
                        break
            except Exception as e :
                print (f"[Plugin System Error]: [ERROR] Не удалось загрузить '{item }': {e }")
