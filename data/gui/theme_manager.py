# -*- coding: utf-8 -*-
# data/gui/theme_manager.py

from tkinter import ttk
from data.core.config_manager import config
from data.core.i18n import t
THEMES ={
"light":{
"key":"theme_light",
"default_name":"Text",
"bg_main":"#f0f0f0",
"bg_card":"#ffffff",
"bg_card_border":"#cbd5e1",
"bg_header":"#ffffff",
"bg_toolbar":"#e2e8f0",
"fg_primary":"#0f172a",
"fg_secondary":"#334155",
"fg_muted":"#64748b",
"accent":"#1976d2",
"accent_hover":"#1565c0",
"accent_text":"#ffffff",
"preset_btn_bg":"#e8eaf6",
"preset_btn_fg":"#1a237e",
"preset_btn_active_bg":"#1976d2",
"preset_btn_active_fg":"#ffffff",
"input_bg":"#ffffff",
"input_fg":"#0f172a",
"input_border":"#94a3b8",
"btn_bg":"#ffffff",
"btn_fg":"#0f172a",
"btn_hover":"#e2e8f0",
"popup_bg":"#1e293b",
"popup_fg":"#f8fafc",
"popup_border":"#475569",
"popup_hint":"#94a3b8",
"status_ready":"#16a34a",
"status_error":"#dc2626",
"help_btn_bg":"#e0f2fe",
"help_btn_fg":"#0284c7",
},
"dark":{
"key":"theme_dark",
"default_name":"Text",
"bg_main":"#18181b",
"bg_card":"#27272a",
"bg_card_border":"#3f3f46",
"bg_header":"#27272a",
"bg_toolbar":"#202023",
"fg_primary":"#f4f4f5",
"fg_secondary":"#d4d4d8",
"fg_muted":"#a1a1aa",
"accent":"#38bdf8",
"accent_hover":"#0284c7",
"accent_text":"#09090b",
"preset_btn_bg":"#3f3f46",
"preset_btn_fg":"#e0e7ff",
"preset_btn_active_bg":"#38bdf8",
"preset_btn_active_fg":"#09090b",
"input_bg":"#18181b",
"input_fg":"#f4f4f5",
"input_border":"#52525b",
"btn_bg":"#3f3f46",
"btn_fg":"#f4f4f5",
"btn_hover":"#52525b",
"popup_bg":"#27272a",
"popup_fg":"#f4f4f5",
"popup_border":"#52525b",
"popup_hint":"#a1a1aa",
"status_ready":"#4ade80",
"status_error":"#f87171",
"help_btn_bg":"#0369a1",
"help_btn_fg":"#e0f2fe",
},
"gray":{
"key":"theme_gray",
"default_name":"Text",
"bg_main":"#2d3035",
"bg_card":"#373a40",
"bg_card_border":"#4e525a",
"bg_header":"#373a40",
"bg_toolbar":"#25272b",
"fg_primary":"#f1f3f5",
"fg_secondary":"#ced4da",
"fg_muted":"#adb5bd",
"accent":"#818cf8",
"accent_hover":"#6366f1",
"accent_text":"#ffffff",
"preset_btn_bg":"#495057",
"preset_btn_fg":"#e7f5ff",
"preset_btn_active_bg":"#818cf8",
"preset_btn_active_fg":"#ffffff",
"input_bg":"#2b2d31",
"input_fg":"#f1f3f5",
"input_border":"#5c6068",
"btn_bg":"#495057",
"btn_fg":"#f1f3f5",
"btn_hover":"#5c636a",
"popup_bg":"#25272b",
"popup_fg":"#f1f3f5",
"popup_border":"#4e525a",
"popup_hint":"#adb5bd",
"status_ready":"#51cf66",
"status_error":"#ff6b6b",
"help_btn_bg":"#4c6ef5",
"help_btn_fg":"#edf2ff",
},
"nord":{
"key":"theme_nord",
"default_name":"Text",
"bg_main":"#242933",
"bg_card":"#2e3440",
"bg_card_border":"#434c5e",
"bg_header":"#2e3440",
"bg_toolbar":"#1e222a",
"fg_primary":"#eceff4",
"fg_secondary":"#d8dee9",
"fg_muted":"#88c0d0",
"accent":"#88c0d0",
"accent_hover":"#81a1c1",
"accent_text":"#2e3440",
"preset_btn_bg":"#3b4252",
"preset_btn_fg":"#88c0d0",
"preset_btn_active_bg":"#88c0d0",
"preset_btn_active_fg":"#2e3440",
"input_bg":"#242933",
"input_fg":"#eceff4",
"input_border":"#4c566a",
"btn_bg":"#3b4252",
"btn_fg":"#eceff4",
"btn_hover":"#434c5e",
"popup_bg":"#2e3440",
"popup_fg":"#eceff4",
"popup_border":"#4c566a",
"popup_hint":"#81a1c1",
"status_ready":"#a3be8c",
"status_error":"#bf616a",
"help_btn_bg":"#434c5e",
"help_btn_fg":"#88c0d0",
},
"ochre":{
"key":"theme_ochre",
"default_name":"Text",
"bg_main":"#2d241e",
"bg_card":"#3a3028",
"bg_card_border":"#54463b",
"bg_header":"#3a3028",
"bg_toolbar":"#241d18",
"fg_primary":"#fef3c7",
"fg_secondary":"#fde68a",
"fg_muted":"#d97706",
"accent":"#d97706",
"accent_hover":"#b45309",
"accent_text":"#ffffff",
"preset_btn_bg":"#4a3e34",
"preset_btn_fg":"#fde68a",
"preset_btn_active_bg":"#d97706",
"preset_btn_active_fg":"#ffffff",
"input_bg":"#28201a",
"input_fg":"#fef3c7",
"input_border":"#5c4d41",
"btn_bg":"#4a3e34",
"btn_fg":"#fef3c7",
"btn_hover":"#5c4d41",
"popup_bg":"#332a23",
"popup_fg":"#fef3c7",
"popup_border":"#54463b",
"popup_hint":"#fde68a",
"status_ready":"#a3e635",
"status_error":"#ef4444",
"help_btn_bg":"#54463b",
"help_btn_fg":"#fbbf24",
}
}

FONT_SIZES ={
"small":{"key":"font_small","default_name":"Text","size":8 },
"normal":{"key":"font_normal","default_name":"Text","size":9 },
"large":{"key":"font_large","default_name":"Text","size":11 },
"huge":{"key":"font_huge","default_name":"Text","size":13 }
}

class ThemeManager :
    def __init__ (self ):
        self .current_theme_key ="light"
        self .current_font_scale ="normal"
        self .base_font_size =9

        self .font_family ="Segoe UI"
        self .load_from_config ()

    def load_from_config (self ):
        self .current_theme_key =config .get_str ("APPEARANCE","Theme","light").lower ()
        if self .current_theme_key not in THEMES :
            self .current_theme_key ="light"

        self .current_font_scale =config .get_str ("APPEARANCE","FontSize","normal").lower ()
        if self .current_font_scale not in FONT_SIZES :
            self .current_font_scale ="normal"

        self .base_font_size =FONT_SIZES [self .current_font_scale ]["size"]

    def set_theme (self ,theme_key ):
        if theme_key in THEMES :
            self .current_theme_key =theme_key
            config .set_value ("APPEARANCE","Theme",theme_key )

    def set_font_size (self ,font_scale ):
        if font_scale in FONT_SIZES :
            self .current_font_scale =font_scale
            self .base_font_size =FONT_SIZES [font_scale ]["size"]
            config .set_value ("APPEARANCE","FontSize",font_scale )

    def get_color (self ,color_key ):
        palette =THEMES .get (self .current_theme_key ,THEMES ["light"])
        return palette .get (color_key ,"#ffffff")

    def font (self ,size_offset =0 ,weight ="normal"):
        size =max (7 ,self .base_font_size +size_offset )
        return (self .font_family ,size ,weight )

    def get_theme_display_options (self ):
        result =[]
        for k ,v in THEMES .items ():
            loc_name =t (v ["key"],v ["default_name"])
            result .append ((k ,loc_name ))
        return result

    def get_font_display_options (self ):
        result =[]
        for k ,v in FONT_SIZES .items ():
            loc_name =t (v ["key"],v ["default_name"])
            result .append ((k ,loc_name ))
        return result

    def apply_ttk_theme (self ,root =None ):
        style =ttk .Style ()
        try :
            style .theme_use ("clam")
        except Exception :pass

        bg_main =self .get_color ("bg_main")
        bg_card =self .get_color ("bg_card")
        fg_pri =self .get_color ("fg_primary")
        accent =self .get_color ("accent")
        accent_text =self .get_color ("accent_text")
        border =self .get_color ("bg_card_border")
        in_bg =self .get_color ("input_bg")
        in_fg =self .get_color ("input_fg")

        style .configure ("TNotebook",background =bg_main ,borderwidth =0 )
        style .configure ("TNotebook.Tab",background =bg_card ,foreground =fg_pri ,font =self .font (0 ),padding =[10 ,4 ])
        style .map ("TNotebook.Tab",background =[("selected",accent )],foreground =[("selected",accent_text )])

        style .configure (
        "TCombobox",
        background =bg_card ,
        fieldbackground =in_bg ,
        foreground =in_fg ,
        darkcolor =border ,
        lightcolor =border ,
        bordercolor =border ,
        arrowcolor =fg_pri ,
        arrowsize =12 ,
        font =self .font (0 ),
        padding =4
        )

        style .map (
        "TCombobox",
        fieldbackground =[
        ("readonly",in_bg ),
        ("disabled",bg_main ),
        ("focus",in_bg ),
        ("!disabled",in_bg )
        ],
        foreground =[
        ("readonly",in_fg ),
        ("disabled",self .get_color ("fg_muted")),
        ("focus",in_fg ),
        ("!disabled",in_fg )
        ],
        background =[
        ("readonly",bg_card ),
        ("disabled",bg_main ),
        ("hover",self .get_color ("btn_hover")),
        ("!disabled",bg_card )
        ],
        arrowcolor =[
        ("disabled",self .get_color ("fg_muted")),
        ("!disabled",fg_pri )
        ]
        )

        style .configure (
        "Vertical.TScrollbar",
        background =border ,
        troughcolor =bg_main ,
        bordercolor =bg_main ,
        arrowcolor =fg_pri ,
        arrowsize =12 ,
        gripcount =0 ,
        width =14
        )
        style .map (
        "Vertical.TScrollbar",
        background =[
        ("pressed",self .get_color ("accent_hover")),
        ("active",accent ),
        ("!disabled",border )
        ]
        )

        if root :
            try :
                root .option_add ('*TCombobox*Listbox.background',in_bg )
                root .option_add ('*TCombobox*Listbox.foreground',in_fg )
                root .option_add ('*TCombobox*Listbox.selectBackground',accent )
                root .option_add ('*TCombobox*Listbox.selectForeground',accent_text )
                root .option_add ('*TCombobox*Listbox.font',self .font (0 ))
            except Exception :pass

        style .configure ("Treeview",background =bg_card ,fieldbackground =bg_card ,foreground =fg_pri ,font =self .font (0 ))
        style .configure ("Treeview.Heading",background =self .get_color ("bg_toolbar"),foreground =fg_pri ,font =self .font (0 ,"bold"))
        style .map ("Treeview",background =[("selected",accent )],foreground =[("selected",accent_text )])

        style .configure ("TProgressbar",background =accent ,troughcolor =in_bg ,bordercolor =border )

theme =ThemeManager ()
