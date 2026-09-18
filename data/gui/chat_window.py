# -*- coding: utf-8 -*-
# data/gui/chat_window.py

import json, re, threading, time
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk
from data.core.api_config import api_config
from data.core.config_manager import config
from data.core.logger import logger
from data.core.web_search import OPENAI_WEB_TOOLS, GEMINI_WEB_TOOLS, execute_tool_call
from data.gui.dialogs import attach_text_context_menu, ToolTip
from data.gui.theme_manager import theme
from data.services.base_service import LOADED_SERVICES
class UniversalChatClient :

    def __init__ (self ,service_id ):
        self .service_id =service_id
        self .model =api_config .get_val (service_id ,"model","")
        self .api_key =api_config .get_val (service_id ,"api_key","")

        self .is_gemini =(service_id =="gemini_family"or "gemini"in self .model .lower ()or "generativelanguage"in api_config .get_val (service_id ,"endpoint",""))

        if self .is_gemini :
            self .endpoint =f"https://generativelanguage.googleapis.com/v1beta/models/{self .model }:generateContent"
        else :
            self .endpoint =api_config .get_val (service_id ,"endpoint","https://api.orcarouter.ai/v1/chat/completions")
            if not self .endpoint :
                self .endpoint ="https://api.orcarouter.ai/v1/chat/completions"

        self .is_cf ="cloudflare"in self .endpoint
        self .is_orca =not self .is_gemini and not self .is_cf

    def _get_opener (self ):
        conn_mode =api_config .get_val (self .service_id ,"connection_mode","doh")
        if conn_mode =="proxy":
            proxy =api_config .get_val (self .service_id ,"proxy","").strip ()
            if proxy :
                return urllib .request .build_opener (urllib .request .ProxyHandler ({"http":proxy ,"https":proxy }))
        return urllib .request .build_opener ()

    def send_chat (self ,history ,enable_search ):
        sys_prompt =(
        "Ты — полезный, умный и вежливый ИИ-ассистент. "
        "Отвечай на вопросы пользователя четко, структурированно и по делу."
        )
        if enable_search :
            sys_prompt +=(
            "\n\nИНСТРУМЕНТЫ ВЕБ-ПОИСКА:\n"
            "Вам доступны инструменты поиска `search_web` (DuckDuckGo) и `fetch_webpage` (чтение ссылок). "
            "Используйте их обязательно, если пользователь просит найти актуальную информацию или дает веб-ссылку."
            )

        opener =self ._get_opener ()

        if self .is_gemini :
            return self ._send_gemini (history ,sys_prompt ,enable_search ,opener )
        elif self .is_orca :
            return self ._send_orca (history ,sys_prompt ,enable_search ,opener )
        else :
            return self ._send_cloudflare (history ,sys_prompt ,opener )

    def _send_orca (self ,history ,sys_prompt ,enable_search ,opener ):
        messages =[{"role":"system","content":sys_prompt }]+history
        headers ={
        "Content-Type":"application/json; charset=utf-8",
        "Authorization":f"Bearer {self .api_key }",
        "Accept":"*/*",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        max_steps =4 if enable_search else 1
        for step in range (max_steps ):
            payload ={
            "model":self .model ,
            "messages":messages ,
            "temperature":0.4
            }

            if "glm"in self .model .lower ():
                payload ["reasoning_effort"]="low"
                payload ["include_reasoning"]=False

            if enable_search and step <(max_steps -1 ):
                payload ["tools"]=OPENAI_WEB_TOOLS

            logger .api_payload (f"Chat: {self .service_id }",self .model ,self .endpoint ,headers ,payload )
            t_call =time .time ()

            try :
                req =urllib .request .Request (self .endpoint ,data =json .dumps (payload ).encode ('utf-8'),headers =headers )
                with opener .open (req ,timeout =70.0 )as resp :
                    raw_bytes =resp .read ()
                    elapsed =time .time ()-t_call
                    raw_str =raw_bytes .decode ('utf-8')
                    data =json .loads (raw_str )

                    logger .api_raw_response (f"Chat: {self .service_id }",resp .status ,elapsed ,raw_str )
                    logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,resp .status )

                if "choices"not in data or not data ["choices"]:
                    return "[Ошибка: пустой ответ от сервера Orca]"

                msg =data ["choices"][0 ]["message"]

                if msg .get ("tool_calls")and enable_search and step <(max_steps -1 ):
                    messages .append ({
                    "role":"assistant",
                    "content":msg .get ("content")or "",
                    "tool_calls":msg ["tool_calls"]
                    })
                    for tc in msg ["tool_calls"]:
                        fn_name =tc .get ("function",{}).get ("name")
                        raw_args =tc .get ("function",{}).get ("arguments","{}")
                        try :args =json .loads (raw_args )
                        except Exception :args ={"query":str (raw_args )}

                        tool_res =execute_tool_call (fn_name ,args )
                        logger .tool_call (f"Chat: {self .service_id }",step +1 ,fn_name ,args ,tool_res )

                        messages .append ({
                        "role":"tool",
                        "tool_call_id":tc .get ("id",""),
                        "name":fn_name ,
                        "content":tool_res
                        })
                    continue

                ans =msg .get ("content")or msg .get ("reasoning_content")or ""
                ans =re .sub (r'<think>[\s\S]*?</think>','',ans ,flags =re .IGNORECASE ).strip ()
                return ans

            except urllib .error .HTTPError as he :
                elapsed =time .time ()-t_call
                err_body =he .read ().decode ("utf-8",errors ="ignore")
                logger .api_raw_response (f"Chat: {self .service_id }",he .code ,elapsed ,err_body )
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,he .code ,note =f"HTTP Error {he .code }")

                if he .code in (400 ,502 ,503 )and step ==0 :
                    payload .pop ("tools",None )
                    time .sleep (0.5 )
                    continue
                if he .code in (500 ,502 ,503 ,504 ):
                    return f"[Сервер перегружен (HTTP {he .code })]: Провайдер временно недоступен. Попробуйте позже."
                if he .code ==429 :
                    return "[Превышен лимит запросов (HTTP 429)]: Слишком много обращений. Подождите немного."
                return f"[Ошибка API HTTP {he .code }]: {err_body [:200 ]}"
            except urllib .error .URLError as ue :
                elapsed =time .time ()-t_call
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,0 ,note =f"URLError: {ue .reason }")
                return f"[Сетевая ошибка OrcaRouter]: {ue .reason }"
            except Exception as e :
                elapsed =time .time ()-t_call
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,0 ,note =f"Exception: {e }")
                return f"[Ошибка OrcaRouter]: {e }"

        return "[Ошибка: превышен лимит шагов агента поиска]"

    def _send_gemini (self ,history ,sys_prompt ,enable_search ,opener ):
        contents =[]
        for h in history :
            role ="model"if h ["role"]=="assistant"else "user"
            contents .append ({"role":role ,"parts":[{"text":h ["content"]}]})

        url =f"https://generativelanguage.googleapis.com/v1beta/models/{self .model }:generateContent"
        headers ={
        "Content-Type":"application/json",
        "x-goog-api-key":self .api_key ,
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        max_steps =4 if enable_search else 1
        for step in range (max_steps ):
            payload ={
            "contents":contents ,
            "systemInstruction":{"parts":[{"text":sys_prompt }]},
            "generationConfig":{"temperature":0.4 }
            }
            if enable_search and step <(max_steps -1 ):
                payload ["tools"]=GEMINI_WEB_TOOLS

            logger .api_payload (f"Chat: {self .service_id }",self .model ,url ,headers ,payload )
            t_call =time .time ()

            try :
                req =urllib .request .Request (url ,data =json .dumps (payload ).encode ('utf-8'),headers =headers )
                with opener .open (req ,timeout =60.0 )as resp :
                    raw_bytes =resp .read ()
                    elapsed =time .time ()-t_call
                    raw_str =raw_bytes .decode ('utf-8')
                    data =json .loads (raw_str )

                    logger .api_raw_response (f"Chat: {self .service_id }",resp .status ,elapsed ,raw_str )
                    logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,resp .status )

            except urllib .error .HTTPError as he :
                elapsed =time .time ()-t_call
                err_body =he .read ().decode ('utf-8',errors ='ignore')
                logger .api_raw_response (f"Chat: {self .service_id }",he .code ,elapsed ,err_body )
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,he .code ,note =f"HTTP Error {he .code }")

                if he .code in (500 ,502 ,503 ,504 ):
                    return f"[Сервер перегружен (HTTP {he .code })]: Модель сейчас испытывает высокую нагрузку. Попробуйте позже."
                if he .code ==429 :
                    return "[Превышен лимит запросов (HTTP 429)]: Достигнута квота Gemini. Подождите немного."
                return f"[Ошибка Gemini HTTP {he .code }]: {err_body [:200 ]}"
            except urllib .error .URLError as ue :
                elapsed =time .time ()-t_call
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,0 ,note =f"URLError: {ue .reason }")
                return f"[Сетевая ошибка Gemini]: {ue .reason }"
            except Exception as e :
                elapsed =time .time ()-t_call
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,0 ,note =f"Exception: {e }")
                return f"[Ошибка Gemini]: {e }"

            cand =data .get ("candidates",[{}])[0 ]
            parts =cand .get ("content",{}).get ("parts",[])

            fn_call =None
            text_res =""
            for p in parts :
                if "functionCall"in p :fn_call =p ["functionCall"]
                if "text"in p :text_res +=p ["text"]

            if fn_call and enable_search and step <(max_steps -1 ):
                fn_name =fn_call .get ("name")
                args =fn_call .get ("args",{})

                contents .append ({"role":"model","parts":[{"functionCall":fn_call }]})
                tool_res =execute_tool_call (fn_name ,args )
                logger .tool_call (f"Chat: {self .service_id }",step +1 ,fn_name ,args ,tool_res )

                contents .append ({
                "role":"user",
                "parts":[{"functionResponse":{"name":fn_name ,"response":{"result":tool_res }}}]
                })
                continue

            return text_res .strip ()

        return "[Ошибка: превышен лимит шагов агента поиска]"

    def _send_cloudflare (self ,history ,sys_prompt ,opener ):
        account_id =api_config .get_val (self .service_id ,"account_id","")
        url =self .endpoint .replace ("{account_id}",account_id ).replace ("{model}",self .model )
        headers ={
        "Content-Type":"application/json",
        "Authorization":f"Bearer {self .api_key }",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

        messages =[{"role":"system","content":sys_prompt }]+history
        payload ={"messages":messages ,"temperature":0.4 }

        logger .api_payload (f"Chat: {self .service_id }",self .model ,url ,headers ,payload )
        t_call =time .time ()

        try :
            req =urllib .request .Request (url ,data =json .dumps (payload ).encode ('utf-8'),headers =headers )
            with opener .open (req ,timeout =50.0 )as resp :
                raw_bytes =resp .read ()
                elapsed =time .time ()-t_call
                raw_str =raw_bytes .decode ('utf-8')
                data =json .loads (raw_str )

                logger .api_raw_response (f"Chat: {self .service_id }",resp .status ,elapsed ,raw_str )
                logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,resp .status )

            res =data .get ("result",{}).get ("response","")
            if not res and data .get ("result",{}).get ("choices"):
                res =data .get ("result")["choices"][0 ].get ("message",{}).get ("content","")
            return res .strip ()
        except urllib .error .HTTPError as he :
            elapsed =time .time ()-t_call
            err_body =he .read ().decode ("utf-8",errors ="ignore")
            logger .api_raw_response (f"Chat: {self .service_id }",he .code ,elapsed ,err_body )
            logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,he .code ,note =f"HTTP Error {he .code }")
            if he .code in (500 ,502 ,503 ,504 ):
                return f"[Сервер перегружен (HTTP {he .code })]: Cloudflare недоступен."
            return f"[Ошибка Cloudflare AI HTTP {he .code }]"
        except urllib .error .URLError as ue :
            elapsed =time .time ()-t_call
            logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,0 ,note =f"URLError: {ue .reason }")
            return f"[Сетевая ошибка Cloudflare]: {ue .reason }"
        except Exception as e :
            elapsed =time .time ()-t_call
            logger .api_summary (f"Chat: {self .service_id }",self .model ,elapsed ,0 ,note =f"Exception: {e }")
            return f"[Ошибка Cloudflare AI]: {e }"

class ChatWindow (tk .Toplevel ):

    def __init__ (self ,parent ):
        super ().__init__ (parent )
        self .parent =parent
        self .history =[]
        self ._is_generating =False

        bg_main =theme .get_color ("bg_main")
        self .title ("Чат с ИИ — QTranslate AI Hub")
        self .configure (bg =bg_main )

        self ._restore_geometry ()
        self ._build_ui ()

        self .protocol ("WM_DELETE_WINDOW",self ._on_close )
        self .after (100 ,lambda :self .t_input .focus_set ())
        logger .system ("Окно чата с ИИ открыто")

    def _restore_geometry (self ):
        x =config .get_int ("CHAT_WINDOW","PosX",-1 )
        y =config .get_int ("CHAT_WINDOW","PosY",-1 )
        w =config .get_int ("CHAT_WINDOW","Width",700 )
        h =config .get_int ("CHAT_WINDOW","Height",600 )

        self .update_idletasks ()
        screen_w =self .winfo_screenwidth ()
        screen_h =self .winfo_screenheight ()

        w =max (480 ,min (w ,screen_w -40 ))
        h =max (380 ,min (h ,screen_h -60 ))

        if 0 <=x <=screen_w -100 and 0 <=y <=screen_h -100 :
            self .geometry (f"{w }x{h }+{x }+{y }")
        else :
            cx =max (0 ,(screen_w -w )//2 )
            cy =max (0 ,(screen_h -h )//2 )
            self .geometry (f"{w }x{h }+{cx }+{cy }")

    def _on_close (self ):
        try :
            w =self .winfo_width ()
            h =self .winfo_height ()
            x =self .winfo_x ()
            y =self .winfo_y ()
            screen_w =self .winfo_screenwidth ()
            screen_h =self .winfo_screenheight ()

            if 400 <=w <=screen_w and 300 <=h <=screen_h and 0 <=x <=screen_w -50 and 0 <=y <=screen_h -50 :
                config .set_value ("CHAT_WINDOW","PosX",str (x ))
                config .set_value ("CHAT_WINDOW","PosY",str (y ))
                config .set_value ("CHAT_WINDOW","Width",str (w ))
                config .set_value ("CHAT_WINDOW","Height",str (h ))
        except Exception :
            pass
        self .destroy ()

    def _get_api_models (self ):
        valid_models ={}
        for s_id ,s_obj in LOADED_SERVICES .items ():
            if not getattr (s_obj ,"is_ai_service",True ):continue
            if s_id in ("chatgpt_web","deepl_web","google_ai","freetranslations","webtran","yandex","yandex_inl","bing"):
                continue
            valid_models [f"{s_obj .name } ({s_id })"]=s_id
        return valid_models

    def _build_ui (self ):
        for widget in self .winfo_children ():widget .destroy ()

        bg_main =theme .get_color ("bg_main")
        bg_card =theme .get_color ("bg_card")
        fg_pri =theme .get_color ("fg_primary")
        in_bg =theme .get_color ("input_bg")
        in_fg =theme .get_color ("input_fg")
        border =theme .get_color ("bg_card_border")

        pad =tk .Frame (self ,bg =bg_main ,padx =12 ,pady =10 )
        pad .pack (fill =tk .BOTH ,expand =True )

        top_bar =tk .Frame (pad ,bg =bg_card ,padx =8 ,pady =6 ,relief =tk .SOLID ,bd =1 ,highlightbackground =border ,highlightthickness =1 )
        top_bar .pack (side =tk .TOP ,fill =tk .X ,pady =(0 ,8 ))

        tk .Label (top_bar ,text ="Модель:",font =theme .font (0 ,"bold"),fg =fg_pri ,bg =bg_card ).pack (side =tk .LEFT ,padx =(0 ,4 ))

        self .model_map =self ._get_api_models ()
        model_names =list (self .model_map .keys ())
        self .combo_model =ttk .Combobox (top_bar ,values =model_names ,state ="readonly",width =28 ,font =theme .font (0 ))
        if model_names :
            self .combo_model .set (model_names [0 ])
        self .combo_model .pack (side =tk .LEFT ,padx =(0 ,10 ))

        self .var_search =tk .BooleanVar (value =True )
        chk_search =tk .Checkbutton (
        top_bar ,text ="Поиск в интернете",variable =self .var_search ,
        bg =bg_card ,fg =fg_pri ,selectcolor =in_bg ,font =theme .font (0 ),cursor ="hand2"
        )
        chk_search .pack (side =tk .LEFT )
        ToolTip (chk_search ,"Разрешить модели искать информацию в сети и переходить по ссылкам")

        btn_clear =tk .Button (
        top_bar ,text ="Очистить чат",font =theme .font (-1 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("help_btn_bg"),fg =theme .get_color ("help_btn_fg"),
        cursor ="hand2",padx =8 ,pady =2 ,command =self ._clear_chat
        )
        btn_clear .pack (side =tk .RIGHT )

        input_frame =tk .Frame (pad ,bg =bg_main )
        input_frame .pack (side =tk .BOTTOM ,fill =tk .X ,pady =(6 ,0 ))

        self .btn_send =tk .Button (
        input_frame ,text ="Отправить",font =theme .font (1 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("accent"),fg =theme .get_color ("accent_text"),
        cursor ="hand2",padx =14 ,pady =10 ,command =self ._send_message
        )
        self .btn_send .pack (side =tk .RIGHT ,fill =tk .Y ,padx =(8 ,0 ))
        ToolTip (self .btn_send ,"Отправить сообщение (Ctrl + Enter)")

        text_border =tk .Frame (input_frame ,relief =tk .SOLID ,bd =1 ,highlightbackground =border ,highlightthickness =1 )
        text_border .pack (side =tk .LEFT ,fill =tk .BOTH ,expand =True )

        self .t_input =tk .Text (text_border ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,wrap =tk .WORD ,height =3 ,bd =0 ,padx =6 ,pady =6 )
        sb_in =ttk .Scrollbar (text_border ,orient ="vertical",command =self .t_input .yview )
        self .t_input .configure (yscrollcommand =sb_in .set )
        sb_in .pack (side =tk .RIGHT ,fill =tk .Y )
        self .t_input .pack (side =tk .LEFT ,fill =tk .BOTH ,expand =True )
        attach_text_context_menu (self .t_input )

        self .t_input .bind ("<Control-Return>",lambda e :self ._send_message ()or "break")

        chat_frame =tk .Frame (pad ,relief =tk .SOLID ,bd =1 ,highlightbackground =border ,highlightthickness =1 )
        chat_frame .pack (side =tk .TOP ,fill =tk .BOTH ,expand =True ,pady =(0 ,0 ))

        self .t_chat =tk .Text (chat_frame ,font =theme .font (1 ),bg =in_bg ,fg =in_fg ,wrap =tk .WORD ,bd =0 ,padx =8 ,pady =8 ,state ="disabled")
        sb_chat =ttk .Scrollbar (chat_frame ,orient ="vertical",command =self .t_chat .yview )
        self .t_chat .configure (yscrollcommand =sb_chat .set )

        self .t_chat .tag_configure ("user_name",foreground =theme .get_color ("accent"),font =theme .font (1 ,"bold"),justify ="right")
        self .t_chat .tag_configure ("user_text",foreground =in_fg ,justify ="right")
        self .t_chat .tag_configure ("ai_name",foreground ="#10b981",font =theme .font (1 ,"bold"),justify ="left")
        self .t_chat .tag_configure ("ai_text",foreground =in_fg ,justify ="left")
        self .t_chat .tag_configure ("sys_text",foreground =theme .get_color ("fg_muted"),font =theme .font (0 ,"italic"),justify ="center")

        sb_chat .pack (side =tk .RIGHT ,fill =tk .Y )
        self .t_chat .pack (side =tk .LEFT ,fill =tk .BOTH ,expand =True )
        attach_text_context_menu (self .t_chat )

        self ._append_to_chat ("sys_text","Чат готов. Сообщения сохраняются в памяти для поддержки контекста диалога.\n")

    def _clear_chat (self ):
        self .history .clear ()
        self .t_chat .config (state ="normal")
        self .t_chat .delete ("1.0",tk .END )
        self .t_chat .config (state ="disabled")
        self ._append_to_chat ("sys_text","История чата очищена.\n")
        self .t_input .focus_set ()

    def _append_to_chat (self ,tag ,text ,is_name =False ):
        self .t_chat .config (state ="normal")
        if is_name :
            self .t_chat .insert (tk .END ,text +"\n",tag )
        else :
            self .t_chat .insert (tk .END ,text +"\n\n",tag )
        self .t_chat .see (tk .END )
        self .t_chat .config (state ="disabled")

    def _send_message (self ):
        if self ._is_generating :return

        user_text =self .t_input .get ("1.0",tk .END ).strip ()
        if not user_text :return

        selected_display =self .combo_model .get ()
        service_id =self .model_map .get (selected_display )
        if not service_id :return

        self .t_input .delete ("1.0",tk .END )
        self ._append_to_chat ("user_name","Вы",is_name =True )
        self ._append_to_chat ("user_text",user_text )

        self .history .append ({"role":"user","content":user_text })

        self ._is_generating =True
        self .btn_send .config (state ="disabled",text ="...")
        self .combo_model .config (state ="readonly")

        threading .Thread (
        target =self ._bg_worker ,
        args =(service_id ,self .var_search .get ()),
        daemon =True
        ).start ()

    def _bg_worker (self ,service_id ,enable_search ):
        client =UniversalChatClient (service_id )

        try :
            response =client .send_chat (self .history ,enable_search )
        except Exception as e :
            response =f"[Системная ошибка]: {e }"

        def _on_finish ():
            self ._is_generating =False
            self .btn_send .config (state ="normal",text ="Отправить")
            self .combo_model .config (state ="readonly")

            self ._append_to_chat ("ai_name",f"ИИ ({client .model })",is_name =True )
            self ._append_to_chat ("ai_text",response )

            if not response .startswith ("[Ошибка")and not response .startswith ("[Сервер"):
                self .history .append ({"role":"assistant","content":response })

            self .t_input .focus_set ()

        self .after (0 ,_on_finish )
