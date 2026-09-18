# -*- coding: utf-8 -*-
# data/gui/wizard_dialog.py
import os
import sys
import json
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk ,messagebox

from data .core .i18n import t
from data .gui .theme_manager import theme
from data .gui .dialog_helpers import HelpPopup ,attach_entry_context_menu ,attach_text_context_menu ,ToolTip
from data .core .service_generator import (
get_next_available_qt_id ,get_known_providers ,get_provider_spec ,
create_unified_service ,test_ping_service ,slugify
)
from data .core .api_config import api_config
from data .core .logger import logger
from data .services .base_service import load_all_services

DOH_PRESET_OPTIONS =[
"Comss.one (SmartDNS / РФ обход)",
"Control D (Uncensored)",
"Cloudflare (1.1.1.1)",
"Google (8.8.8.8)"
]

THINKING_POLICY_OPTIONS =[
("none","Отключено (Стандартные модели: Cerebras, Mistral, Llama)"),
("disabled_type","thinking.type: disabled (DeepSeek, Kimi, Boltch)"),
("exclude_reasoning","reasoning.max_tokens: 0 (OpenRouter)"),
("enable_thinking_false","enable_thinking: false (Alibaba DashScope / Qwen)"),
("reasoning_effort_low","reasoning_effort: low (GLM, OpenAI, Kimi K3)")
]

WIZARD_HELP_FALLBACK ={
"provider":(
"ПОСТАВЩИК / АГРЕГАТОР\n\n"
"Шаблоны автоматически считываются из папки data/core/templates/:\n"
"* Cerebras — сверхскоростной аппаратный инференс (Llama 3.1/3.3).\n"
"* SiliconFlow — агрегатор с бесплатными квотами (DeepSeek V3, Qwen 2.5 72B).\n"
"* Mistral AI — официальные модели Mistral Small, Codestral.\n"
"* Pollinations AI — бесплатные анонимные запросы без обязательного ключа.\n"
"* Boltch.cloud — бесплатный ротационный пул (free:kimi, free:deepseek).\n"
"* OpenRouter.ai — модели :free с поддержкой SOCKS5.\n"
"* Alibaba DashScope — Qwen Turbo / Plus / Max (1M токенов).\n"
"* DeepSeek Official — официальный прямой API.\n"
"* Пользовательский шаблон — ручная настройка любых URL и заголовков с нуля."
),
"name":(
"НАЗВАНИЕ СЕРВИСА\n\n"
"Отображаемое имя, которое появится на кнопке в QTranslate и в шапке карточки в Хабе."
),
"id":(
"СИСТЕМНЫЙ ID / ПАПКА\n\n"
"Уникальное имя папки на английском языке (формируется автоматически из названия)."
),
"model":(
"ИДЕНТИФИКАТОР МОДЕЛИ\n\n"
"Точный системный ID модели в API (например: llama3.1-8b, deepseek-ai/DeepSeek-V3, qwen-turbo)."
),
"endpoint":(
"ЭНДПОИНТ (URL)\n\n"
"Полный веб-адрес до точки /chat/completions на сервере провайдера."
),
"api_key":(
"API КЛЮЧ\n\n"
"Токен доступа к выбранной платформе. Если вы уже вводили ключ этого агрегатора ранее, Хаб подставит его автоматически из providers.ini."
),
"connection":(
"РЕЖИМ СЕТИ\n\n"
"* direct — прямое подключение.\n"
"* proxy — через SOCKS5-прокси (RFC 1928).\n"
"* doh — через DoH SmartDNS (для обхода блокировок в РФ)."
),
"thinking":(
"ПОЛИТИКА РАЗМЫШЛЕНИЙ\n\n"
"Способ подавления раздутых рассуждений модели, чтобы перевод отдавался за 1-3 секунды вместо 40."
),
"path":(
"ПУТЬ К ТЕКСТУ ОТВЕТА (JSON Path)\n\n"
"Указывает скрипту, из какого вложенного поля ответа забрать сам перевод.\n\n"
"* Стандарт: choices.0.message.content\n"
"* Для 99% нейросетей в мире менять это значение НЕ НУЖНО."
),
"qt_id":(
"ID КНОПКИ В QTRANSLATE\n\n"
"Уникальный системный номер кнопки в QTranslate (выбирается автоматически, например 711, 712)."
)
}

def open_file_in_smart_editor (file_path ,parent_window =None ):
    if not file_path or not os .path .exists (file_path ):
        return

    editor_setting ="auto"
    try :
        from data .core .config_manager import config
        editor_setting =config .get_str ("GENERAL","CodeEditor","auto").strip ()
    except Exception :
        pass

    if editor_setting .lower ()=="builtin":
        CodeEditorDialog (parent_window ,file_path )
        return

    if editor_setting !="auto"and os .path .exists (editor_setting ):
        try :
            subprocess .Popen ([editor_setting ,file_path ])
            return
        except Exception :
            pass

    candidates =[
    os .path .expandvars (r"%ProgramFiles%\Notepad++\notepad++.exe"),
    os .path .expandvars (r"%ProgramFiles(x86)%\Notepad++\notepad++.exe"),
    os .path .expandvars (r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
    os .path .expandvars (r"%ProgramFiles%\Sublime Text\sublime_text.exe"),
    os .path .expandvars (r"%ProgramFiles%\Sublime Text 3\sublime_text.exe"),
    ]
    for exe in candidates :
        if os .path .exists (exe ):
            try :
                subprocess .Popen ([exe ,file_path ])
                return
            except Exception :
                pass

    CodeEditorDialog (parent_window ,file_path )

class CodeEditorDialog (tk .Toplevel ):
    def __init__ (self ,parent ,file_path ):
        super ().__init__ (parent )
        self .parent =parent
        self .file_path =file_path

        bg_main =theme .get_color ("bg_main")
        fg_pri =theme .get_color ("fg_primary")
        in_bg =theme .get_color ("input_bg")
        in_fg =theme .get_color ("input_fg")

        filename =os .path .basename (file_path )
        self .title (f"Редактор кода — {filename }")
        self .geometry ("740x560")
        self .minsize (520 ,380 )
        self .configure (bg =bg_main )
        self .transient (parent )
        self .grab_set ()

        pad =tk .Frame (self ,bg =bg_main ,padx =12 ,pady =10 )
        pad .pack (fill =tk .BOTH ,expand =True )

        top_bar =tk .Frame (pad ,bg =bg_main )
        top_bar .pack (fill =tk .X ,pady =(0 ,6 ))

        tk .Label (
        top_bar ,text =f"Файл: {file_path }",
        font =theme .font (-1 ,"bold"),fg =theme .get_color ("accent"),bg =bg_main
        ).pack (side =tk .LEFT )

        text_border =tk .Frame (pad ,relief =tk .SOLID ,bd =1 ,bg =in_bg )
        text_border .pack (fill =tk .BOTH ,expand =True ,pady =(0 ,10 ))

        font_to_use =("Consolas",10 )if sys .platform .startswith ("win")else theme .font (0 )
        self .code_text =tk .Text (
        text_border ,font =font_to_use ,bg =in_bg ,fg =in_fg ,
        wrap =tk .NONE ,bd =0 ,padx =8 ,pady =8
        )

        sb_y =ttk .Scrollbar (text_border ,orient ="vertical",command =self .code_text .yview )
        sb_x =ttk .Scrollbar (text_border ,orient ="horizontal",command =self .code_text .xview )
        self .code_text .configure (yscrollcommand =sb_y .set ,xscrollcommand =sb_x .set )

        sb_y .pack (side =tk .RIGHT ,fill =tk .Y )
        sb_x .pack (side =tk .BOTTOM ,fill =tk .X )
        self .code_text .pack (side =tk .LEFT ,fill =tk .BOTH ,expand =True )
        attach_text_context_menu (self .code_text )

        self ._load_content ()

        btn_bar =tk .Frame (pad ,bg =bg_main )
        btn_bar .pack (fill =tk .X ,side =tk .BOTTOM )

        tk .Button (
        btn_bar ,text ="Закрыть",font =theme .font (0 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("btn_bg"),fg =fg_pri ,padx =16 ,pady =4 ,cursor ="hand2",
        command =self .destroy
        ).pack (side =tk .RIGHT ,padx =(6 ,0 ))

        tk .Button (
        btn_bar ,text ="Сохранить файл",font =theme .font (0 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("accent"),fg =theme .get_color ("accent_text"),
        cursor ="hand2",padx =18 ,pady =4 ,command =self ._save_content
        ).pack (side =tk .RIGHT )

    def _load_content (self ):
        if os .path .exists (self .file_path ):
            try :
                with open (self .file_path ,"r",encoding ="utf-8")as f :
                    content =f .read ()
                self .code_text .insert ("1.0",content )
            except Exception as e :
                self .code_text .insert ("1.0",f"# Ошибка чтения файла: {e }")

    def _save_content (self ):
        content =self .code_text .get ("1.0",tk .END )
        try :
            with open (self .file_path ,"w",encoding ="utf-8")as f :
                f .write (content )
            load_all_services ()
            logger .system (f"Встроенный редактор: файл {self .file_path } сохранен пользователем")
            messagebox .showinfo ("Сохранено",f"Файл успешно сохранен на диске!\n{self .file_path }",parent =self )
        except Exception as e :
            messagebox .showerror ("Ошибка сохранения",f"Не удалось записать файл:\n{e }",parent =self )

class AddServiceWizardDialog (tk .Toplevel ):
    def __init__ (self ,parent ,on_created_callback =None ):
        super ().__init__ (parent )
        self .parent =parent
        self .on_created =on_created_callback
        self ._active_help_popup =None

        self .last_created_slug =None
        self .last_py_path =None
        self .last_js_path =None

        bg_main =theme .get_color ("bg_main")
        self .title ("Студия подключения сервисов — QTranslate AI Hub")
        self .geometry ("680x720")
        self .minsize (620 ,600 )
        self .configure (bg =bg_main )
        self .transient (parent )
        self .grab_set ()

        self ._build_ui ()
        self ._center_window ()
        self ._on_provider_change ()

    def _center_window (self ):
        self .update_idletasks ()
        pw =self .parent .winfo_width ()if self .parent else 600
        ph =self .parent .winfo_height ()if self .parent else 400
        px =self .parent .winfo_rootx ()if self .parent else 200
        py =self .parent .winfo_rooty ()if self .parent else 150
        w ,h =680 ,720
        x =px +max (0 ,(pw -w )//2 )
        y =py +max (0 ,(ph -h )//2 )
        self .geometry (f"{w }x{h }+{x }+{y }")

    def _show_help (self ,anchor_widget ,help_key ):
        if self ._active_help_popup and self ._active_help_popup .winfo_exists ():
            self ._active_help_popup .destroy ()
        text =WIZARD_HELP_FALLBACK .get (help_key ,"")
        if text :
            self ._active_help_popup =HelpPopup (anchor_widget ,text )

    def _create_help_btn (self ,parent ,help_key ):
        btn =tk .Label (
        parent ,text ="?",font =theme .font (-1 ,"bold"),
        fg =theme .get_color ("help_btn_fg"),bg =theme .get_color ("help_btn_bg"),
        relief =tk .FLAT ,bd =0 ,padx =4 ,pady =0 ,cursor ="hand2"
        )
        btn .bind ("<Button-1>",lambda e ,k =help_key ,w =btn :self ._show_help (w ,k ))
        return btn

    def _build_ui (self ):
        bg_main =theme .get_color ("bg_main")
        bg_card =theme .get_color ("bg_card")
        fg_pri =theme .get_color ("fg_primary")
        in_bg =theme .get_color ("input_bg")
        in_fg =theme .get_color ("input_fg")
        border =theme .get_color ("bg_card_border")

        pad =tk .Frame (self ,bg =bg_main ,padx =14 ,pady =10 )
        pad .pack (fill =tk .BOTH ,expand =True )

        header_box =tk .Frame (pad ,bg =bg_main )
        header_box .pack (fill =tk .X ,pady =(0 ,6 ))

        tk .Label (
        header_box ,text ="Студия подключения и настройки сервисов",
        font =theme .font (2 ,"bold"),fg =theme .get_color ("accent"),bg =bg_main
        ).pack (side =tk .LEFT )

        canvas_frame =tk .Frame (pad ,bg =bg_main )
        canvas_frame .pack (fill =tk .BOTH ,expand =True )

        self .canvas =tk .Canvas (canvas_frame ,bg =bg_main ,highlightthickness =0 )
        sb =ttk .Scrollbar (canvas_frame ,orient ="vertical",command =self .canvas .yview )
        self .form_inner =tk .Frame (self .canvas ,bg =bg_card ,padx =12 ,pady =10 ,relief =tk .SOLID ,bd =1 ,highlightbackground =border ,highlightthickness =1 )

        self .form_window =self .canvas .create_window ((0 ,0 ),window =self .form_inner ,anchor ="nw")
        self .canvas .configure (yscrollcommand =sb .set )
        self .canvas .bind ("<Configure>",lambda e :self .canvas .itemconfig (self .form_window ,width =e .width ))
        self .form_inner .bind ("<Configure>",lambda e :self .canvas .configure (scrollregion =self .canvas .bbox ("all")))

        self .canvas .pack (side =tk .LEFT ,fill =tk .BOTH ,expand =True )
        sb .pack (side =tk .RIGHT ,fill =tk .Y )

        r_prov =tk .Frame (self .form_inner ,bg =bg_card )
        r_prov .pack (fill =tk .X ,pady =3 )
        tk .Label (r_prov ,text ="Провайдер / Шаблон:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_prov ,"provider").pack (side =tk .LEFT ,padx =(0 ,6 ))

        self .provider_items =get_known_providers ()
        self .prov_display_names =[name for _ ,name in self .provider_items ]
        self .prov_map ={name :key for key ,name in self .provider_items }

        self .combo_prov =ttk .Combobox (r_prov ,values =self .prov_display_names ,state ="readonly",width =34 )
        if self .prov_display_names :
            self .combo_prov .set (self .prov_display_names [0 ])
        self .combo_prov .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        self .combo_prov .bind ("<<ComboboxSelected>>",self ._on_provider_change )

        r_name =tk .Frame (self .form_inner ,bg =bg_card )
        r_name .pack (fill =tk .X ,pady =3 )
        tk .Label (r_name ,text ="Название сервиса:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_name ,"name").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_name =tk .Entry (r_name ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_name .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        self .e_name .bind ("<KeyRelease>",self ._auto_fill_id )
        attach_entry_context_menu (self .e_name )

        r_id =tk .Frame (self .form_inner ,bg =bg_card )
        r_id .pack (fill =tk .X ,pady =3 )
        tk .Label (r_id ,text ="ID папки / сервиса:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_id ,"id").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_id =tk .Entry (r_id ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_id .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        attach_entry_context_menu (self .e_id )

        r_mod =tk .Frame (self .form_inner ,bg =bg_card )
        r_mod .pack (fill =tk .X ,pady =3 )
        tk .Label (r_mod ,text ="Идентификатор модели:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_mod ,"model").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_model =tk .Entry (r_mod ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_model .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        attach_entry_context_menu (self .e_model )

        r_ep =tk .Frame (self .form_inner ,bg =bg_card )
        r_ep .pack (fill =tk .X ,pady =3 )
        tk .Label (r_ep ,text ="Эндпоинт (URL):",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_ep ,"endpoint").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_endpoint =tk .Entry (r_ep ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_endpoint .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        attach_entry_context_menu (self .e_endpoint )

        r_key =tk .Frame (self .form_inner ,bg =bg_card )
        r_key .pack (fill =tk .X ,pady =3 )
        tk .Label (r_key ,text ="API Ключ провайдера:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_key ,"api_key").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_api_key =tk .Entry (r_key ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_api_key .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        attach_entry_context_menu (self .e_api_key )

        r_net =tk .Frame (self .form_inner ,bg =bg_card )
        r_net .pack (fill =tk .X ,pady =3 )
        tk .Label (r_net ,text ="Режим сети:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_net ,"connection").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .combo_net =ttk .Combobox (r_net ,values =["direct","proxy (SOCKS5)","doh (SmartDNS)"],state ="readonly",width =22 )
        self .combo_net .set ("direct")
        self .combo_net .pack (side =tk .LEFT )
        self .combo_net .bind ("<<ComboboxSelected>>",self ._toggle_net_fields )

        self .r_proxy =tk .Frame (self .form_inner ,bg =bg_card )
        tk .Label (self .r_proxy ,text ="Адрес SOCKS5 (хост:порт):",font =theme .font (-1 ,"bold"),fg =fg_pri ,width =22 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self .e_proxy =tk .Entry (self .r_proxy ,font =theme .font (-1 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_proxy .insert (0 ,"213.165.38.49:1080")
        self .e_proxy .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        attach_entry_context_menu (self .e_proxy )

        self .r_doh =tk .Frame (self .form_inner ,bg =bg_card )
        tk .Label (self .r_doh ,text ="DoH Пресет:",font =theme .font (-1 ,"bold"),fg =fg_pri ,width =22 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self .combo_doh =ttk .Combobox (self .r_doh ,values =DOH_PRESET_OPTIONS ,state ="readonly",width =30 )
        self .combo_doh .set (DOH_PRESET_OPTIONS [0 ])
        self .combo_doh .pack (side =tk .LEFT )

        r_think =tk .Frame (self .form_inner ,bg =bg_card )
        r_think .pack (fill =tk .X ,pady =3 )
        tk .Label (r_think ,text ="Размышления (Thinking):",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_think ,"thinking").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .combo_think =ttk .Combobox (r_think ,values =[name for _ ,name in THINKING_POLICY_OPTIONS ],state ="readonly")
        self .combo_think .set (THINKING_POLICY_OPTIONS [0 ][1 ])
        self .combo_think .pack (side =tk .LEFT ,fill =tk .X ,expand =True )

        r_qtid =tk .Frame (self .form_inner ,bg =bg_card )
        r_qtid .pack (fill =tk .X ,pady =3 )
        tk .Label (r_qtid ,text ="ID кнопки в QTranslate:",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_qtid ,"qt_id").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_qtid =tk .Entry (r_qtid ,font =theme .font (0 ,"bold"),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 ,width =10 )
        self .e_qtid .insert (0 ,str (get_next_available_qt_id ()))
        self .e_qtid .pack (side =tk .LEFT )
        attach_entry_context_menu (self .e_qtid )

        r_path =tk .Frame (self .form_inner ,bg =bg_card )
        r_path .pack (fill =tk .X ,pady =(3 ,1 ))
        tk .Label (r_path ,text ="Путь ответа (JSON Path):",font =theme .font (0 ,"bold"),fg =fg_pri ,width =19 ,anchor ="w",bg =bg_card ).pack (side =tk .LEFT )
        self ._create_help_btn (r_path ,"path").pack (side =tk .LEFT ,padx =(0 ,6 ))
        self .e_path =tk .Entry (r_path ,font =theme .font (0 ),bg =in_bg ,fg =in_fg ,relief =tk .SOLID ,bd =1 )
        self .e_path .insert (0 ,"choices.0.message.content")
        self .e_path .pack (side =tk .LEFT ,fill =tk .X ,expand =True )
        attach_entry_context_menu (self .e_path )

        tk .Label (
        self .form_inner ,
        text ="* По умолчанию: choices.0.message.content (для 99% нейросетей менять не нужно)",
        font =theme .font (-2 ,"italic"),fg =theme .get_color ("fg_muted"),bg =bg_card
        ).pack (anchor ="w",padx =(27 ,0 ),pady =(0 ,4 ))

        self .action_panel =tk .LabelFrame (
        pad ,text =" Тестирование и проверка созданного сервиса ",
        font =theme .font (0 ,"bold"),fg =theme .get_color ("accent"),bg =bg_card ,padx =10 ,pady =8
        )

        self .lbl_status_badge =tk .Label (
        self .action_panel ,text ="Сервис успешно создан. QTranslate перезапущен.",
        font =theme .font (0 ,"bold"),fg =theme .get_color ("status_ready"),bg =bg_card
        )
        self .lbl_status_badge .pack (anchor ="w",pady =(0 ,6 ))

        r_test_btns =tk .Frame (self .action_panel ,bg =bg_card )
        r_test_btns .pack (fill =tk .X ,pady =2 )

        self .btn_ping_fast =tk .Button (
        r_test_btns ,text ="Быстрый пинг (Hello)",font =theme .font (-1 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("btn_bg"),fg =fg_pri ,cursor ="hand2",padx =8 ,pady =2 ,
        command =self ._on_fast_ping
        )
        self .btn_ping_fast .pack (side =tk .LEFT ,padx =(0 ,6 ))

        self .btn_ping_full =tk .Button (
        r_test_btns ,text ="Полный пинг (Сырой ответ)",font =theme .font (-1 ),relief =tk .FLAT ,
        bg =theme .get_color ("btn_bg"),fg =fg_pri ,cursor ="hand2",padx =8 ,pady =2 ,
        command =self ._on_full_ping
        )
        self .btn_ping_full .pack (side =tk .LEFT ,padx =(0 ,10 ))

        self .btn_edit_py =tk .Button (
        r_test_btns ,text ="Открыть service.py",font =theme .font (-1 ),relief =tk .FLAT ,
        bg =theme .get_color ("help_btn_bg"),fg =theme .get_color ("help_btn_fg"),cursor ="hand2",padx =6 ,pady =2 ,
        command =self ._on_edit_py
        )
        self .btn_edit_py .pack (side =tk .LEFT ,padx =(0 ,4 ))
        ToolTip (self .btn_edit_py ,"Открыть код плагина в Notepad++ или встроенном редакторе")

        self .btn_edit_js =tk .Button (
        r_test_btns ,text ="Открыть service.js",font =theme .font (-1 ),relief =tk .FLAT ,
        bg =theme .get_color ("help_btn_bg"),fg =theme .get_color ("help_btn_fg"),cursor ="hand2",padx =6 ,pady =2 ,
        command =self ._on_edit_js
        )
        self .btn_edit_js .pack (side =tk .LEFT )
        ToolTip (self .btn_edit_js ,"Открыть JS-скрипт кнопки в Notepad++ или встроенном редакторе")

        btn_bar =tk .Frame (pad ,bg =bg_main )
        btn_bar .pack (fill =tk .X ,side =tk .BOTTOM ,pady =(8 ,0 ))

        self .btn_close =tk .Button (
        btn_bar ,text ="Закрыть",font =theme .font (0 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("btn_bg"),fg =fg_pri ,padx =16 ,pady =4 ,cursor ="hand2",
        command =self .destroy
        )
        self .btn_close .pack (side =tk .RIGHT ,padx =(8 ,0 ))

        self .btn_create =tk .Button (
        btn_bar ,text ="Создать сервис",font =theme .font (0 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("accent"),fg =theme .get_color ("accent_text"),
        cursor ="hand2",padx =18 ,pady =4 ,command =self ._on_create
        )
        self .btn_create .pack (side =tk .RIGHT )

    def _toggle_net_fields (self ,event =None ):
        mode_raw =self .combo_net .get ()
        self .r_proxy .pack_forget ()
        self .r_doh .pack_forget ()

        if "proxy"in mode_raw :
            self .r_proxy .pack (fill =tk .X ,pady =2 ,padx =(27 ,0 ))
        elif "doh"in mode_raw :
            self .r_doh .pack (fill =tk .X ,pady =2 ,padx =(27 ,0 ))

    def _on_provider_change (self ,event =None ):
        chosen_name =self .combo_prov .get ()
        p_key =self .prov_map .get (chosen_name ,"custom")
        spec =get_provider_spec (p_key )

        if p_key !="custom":
            self .e_name .delete (0 ,tk .END )
            self .e_name .insert (0 ,spec ["name"])
            self ._auto_fill_id ()

            self .e_model .delete (0 ,tk .END )
            self .e_model .insert (0 ,spec ["default_model"])

            self .e_endpoint .delete (0 ,tk .END )
            self .e_endpoint .insert (0 ,spec ["endpoint"])

            self .e_path .delete (0 ,tk .END )
            self .e_path .insert (0 ,spec .get ("response_path","choices.0.message.content"))

            saved_key =api_config .get_provider_val (p_key ,"api_key","")
            self .e_api_key .delete (0 ,tk .END )
            self .e_api_key .insert (0 ,saved_key )

            saved_mode =api_config .get_provider_val (p_key ,"connection_mode",spec .get ("connection_mode","direct"))
            if saved_mode =="proxy":
                self .combo_net .set ("proxy (SOCKS5)")
            elif saved_mode =="doh":
                self .combo_net .set ("doh (SmartDNS)")
            else :
                self .combo_net .set ("direct")

            saved_proxy =api_config .get_provider_val (p_key ,"proxy",spec .get ("proxy","213.165.38.49:1080"))
            self .e_proxy .delete (0 ,tk .END )
            self .e_proxy .insert (0 ,saved_proxy )

            target_pol =spec .get ("thinking_policy","none")
            for key ,display in THINKING_POLICY_OPTIONS :
                if key ==target_pol :
                    self .combo_think .set (display )
                    break
        else :
            self .e_name .delete (0 ,tk .END )
            self .e_id .delete (0 ,tk .END )
            self .e_model .delete (0 ,tk .END )
            self .e_endpoint .delete (0 ,tk .END )
            self .e_endpoint .insert (0 ,"https://api.example.com/v1/chat/completions")
            self .e_api_key .delete (0 ,tk .END )
            self .combo_net .set ("direct")
            self .combo_think .set (THINKING_POLICY_OPTIONS [0 ][1 ])

        self ._toggle_net_fields ()

    def _auto_fill_id (self ,event =None ):
        name =self .e_name .get ().strip ()
        slug =slugify (name )
        self .e_id .delete (0 ,tk .END )
        self .e_id .insert (0 ,slug )

    def _get_thinking_policy_key (self ):
        chosen_display =self .combo_think .get ()
        for k ,name in THINKING_POLICY_OPTIONS :
            if name ==chosen_display :
                return k
        return "none"

    def _on_create (self ):
        chosen_prov_name =self .combo_prov .get ()
        p_key =self .prov_map .get (chosen_prov_name ,"custom")

        name =self .e_name .get ().strip ()
        slug =self .e_id .get ().strip ()
        model_id =self .e_model .get ().strip ()
        endpoint =self .e_endpoint .get ().strip ()
        api_key =self .e_api_key .get ().strip ()
        qt_id_val =self .e_qtid .get ().strip ()

        net_mode_raw =self .combo_net .get ()
        conn_mode ="proxy"if "proxy"in net_mode_raw else ("doh"if "doh"in net_mode_raw else "direct")
        proxy_val =self .e_proxy .get ().strip ()
        doh_preset_val =self .combo_doh .get ().strip ()

        thinking_policy =self ._get_thinking_policy_key ()
        response_path =self .e_path .get ().strip ()or "choices.0.message.content"

        spec =get_provider_spec (p_key )
        auth_type =spec .get ("auth_header_type","Bearer")
        extra_headers =json .dumps (spec .get ("extra_headers",{}))

        if not name or not slug or not model_id or not endpoint :
            messagebox .showwarning ("Внимание","Заполните все обязательные поля (Название, ID, Модель, Эндпоинт)!",parent =self )
            return

        self .btn_create .config (state ="disabled",text ="Создание...")

        try :
            ok ,clean_slug ,py_path ,js_path =create_unified_service (
            provider_key =p_key ,
            service_name =name ,
            service_slug =slug ,
            model_id =model_id ,
            endpoint =endpoint ,
            qt_id =qt_id_val ,
            auth_header_type =auth_type ,
            thinking_policy =thinking_policy ,
            response_path =response_path ,
            extra_headers_json =extra_headers ,
            api_key =api_key ,
            connection_mode =conn_mode ,
            proxy =proxy_val ,
            doh_preset =doh_preset_val
            )

            self .last_created_slug =clean_slug
            self .last_py_path =py_path
            self .last_js_path =js_path

            self .lbl_status_badge .config (
            text =f"Сервис '{name }' успешно создан! QTranslate перезапущен (ID: {qt_id_val }).",
            fg =theme .get_color ("status_ready")
            )
            self .action_panel .pack (fill =tk .X ,side =tk .BOTTOM ,pady =(0 ,6 ))

            if self .on_created :
                self .on_created ()

            self .btn_create .config (state ="normal",text ="Обновить сервис")

        except Exception as e :
            self .btn_create .config (state ="normal",text ="Создать сервис")
            logger .system (f"Студия создания Ошибка: {e }")
            messagebox .showerror ("Ошибка",f"Не удалось создать сервис:\n{e }",parent =self )

    def _on_fast_ping (self ):
        if not self .last_created_slug :
            return
        self .btn_ping_fast .config (state ="disabled",text ="Пинг...")

        def _worker ():
            ok ,res ,elapsed =test_ping_service (
            self .last_created_slug ,
            text ="Hello world! This is a test ping.",
            src ="en",trg ="ru"
            )
            def _ui ():
                self .btn_ping_fast .config (state ="normal",text ="Быстрый пинг (Hello)")
                if ok :
                    msg =f"Успех ({elapsed }с):\n\n{res }"
                    messagebox .showinfo ("Пинг успешен",msg ,parent =self )
                else :
                    msg =f"Ошибка ({elapsed }с):\n\n{res }"
                    messagebox .showerror ("Ошибка пинга",msg ,parent =self )
            self .after (0 ,_ui )

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _on_full_ping (self ):
        if not self .last_created_slug :
            return
        self .btn_ping_full .config (state ="disabled",text ="Запрос...")

        def _worker ():
            ok ,res ,elapsed =test_ping_service (
            self .last_created_slug ,
            text ="Compatibility with Automatron and Far Harbor. Testing raw response payload.",
            src ="en",trg ="ru"
            )
            def _ui ():
                self .btn_ping_full .config (state ="normal",text ="Полный пинг (Сырой ответ)")
                self ._show_raw_dialog (res ,elapsed ,ok )
            self .after (0 ,_ui )

        threading .Thread (target =_worker ,daemon =True ).start ()

    def _show_raw_dialog (self ,text ,elapsed ,ok ):
        dlg =tk .Toplevel (self )
        dlg .title (f"Отчет тестирования ({elapsed }с)")
        dlg .geometry ("560x400")
        dlg .configure (bg =theme .get_color ("bg_main"))
        dlg .transient (self )
        dlg .grab_set ()

        pad =tk .Frame (dlg ,bg =theme .get_color ("bg_main"),padx =12 ,pady =12 )
        pad .pack (fill =tk .BOTH ,expand =True )

        status_text =f"Статус: {'Успешно'if ok else 'Сбой'} | Время отклика: {elapsed }с"
        tk .Label (
        pad ,text =status_text ,font =theme .font (1 ,"bold"),
        fg =theme .get_color ("status_ready"if ok else "status_error"),bg =theme .get_color ("bg_main")
        ).pack (anchor ="w",pady =(0 ,6 ))

        t_border =tk .Frame (pad ,relief =tk .SOLID ,bd =1 ,bg =theme .get_color ("input_bg"))
        t_border .pack (fill =tk .BOTH ,expand =True ,pady =(0 ,10 ))

        t_box =tk .Text (t_border ,font =theme .font (0 ),bg =theme .get_color ("input_bg"),fg =theme .get_color ("input_fg"),wrap =tk .WORD ,bd =0 )
        sb =tk .Scrollbar (t_border ,command =t_box .yview )
        t_box .configure (yscrollcommand =sb .set )
        sb .pack (side =tk .RIGHT ,fill =tk .Y )
        t_box .pack (side =tk .LEFT ,fill =tk .BOTH ,expand =True ,padx =4 ,pady =4 )

        t_box .insert ("1.0",text )
        attach_text_context_menu (t_box )

        tk .Button (
        pad ,text ="Закрыть",font =theme .font (0 ,"bold"),relief =tk .FLAT ,
        bg =theme .get_color ("btn_bg"),fg =theme .get_color ("fg_primary"),
        cursor ="hand2",padx =16 ,pady =4 ,command =dlg .destroy
        ).pack (anchor ="e")

    def _on_edit_py (self ):
        if self .last_py_path and os .path .exists (self .last_py_path ):
            open_file_in_smart_editor (self .last_py_path ,self )

    def _on_edit_js (self ):
        if self .last_js_path and os .path .exists (self .last_js_path ):
            open_file_in_smart_editor (self .last_js_path ,self )
