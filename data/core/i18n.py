# -*- coding: utf-8 -*-
# data/core/i18n.py
import os
import sys
import json
import ctypes

def get_base_dir ():
    if getattr (sys ,'frozen',False ):
        return os .path .dirname (sys .executable )
    current_dir =os .path .dirname (os .path .abspath (__file__ ))
    return os .path .abspath (os .path .join (current_dir ,"..",".."))

KNOWN_LANG_NAMES ={
"ru":"Русский",
"en":"English",
"de":"Deutsch",
"fr":"Français",
"es":"Español",
"zh":"简体中文",
"zh-cn":"简体中文",
"zh-tw":"繁體中文",
"cs":"Čeština",
"tr":"Türkçe",
"it":"Italiano",
"pl":"Polski",
"uk":"Українська",
"ja":"日本語",
"ko":"한국어",
"pt":"Português"
}

DEFAULT_LOCALES ={
"ru":{
"__lang_name__":"Русский",

"app_title":"QTranslate AI Hub",
"services_title":"ПОДКЛЮЧЕННЫЕ НЕЙРОСЕТИ И ПЕРЕВОДЧИКИ",
"add_service":"+ Добавить сервис из шаблона",
"btn_browser":"Браузер",
"tip_browser":"Открыть окно браузера",
"btn_ocr":"📸 Снимок OCR",
"tip_ocr":"Сканирование текста с экрана с передачей в QTranslate, выделите нужную область мышью.",
"tip_ocr_settings":"Настройка OCR",
"btn_dict":"📚 Словарь",
"tip_dict":"Словарь терминов и умный глоссарий",
"btn_batch":"📁 Пакетный перевод",
"tip_batch":"Пакетный перевод файлов и модов",
"btn_settings":"⚙️ Настройки",
"tip_settings":"Настройки программы",

"status_ready":"Готов",
"status_not_ready":"Не готов",
"tip_service_settings":"Параметры сервиса",
"tip_service_delete":"Удалить сервис и все его файлы",
"tip_add_preset":"Создать новый пресет",
"tip_edit_preset":"Редактировать активный пресет",
"tip_select_preset":"Выбрать стиль: {name}",
"param_temp":"temperature",
"param_topp":"top_p",
"param_tokens":"max_tokens",
"param_thinking":"Рассуждения",
"param_glossary":"Словарь",

"help_temp":"🌡️ ТЕМПЕРАТУРА\n(temperature, 0.0 - 1.0)\n\nОтвечает за строгость и\nпредсказуемость перевода.\n\n• Меньше (0.0 - 0.2):\nПеревод максимально точный,\nстрогий и буквальный.\nИдеально для интерфейсов,\nкода и документов.\n\n• Больше (0.7 - 1.0):\nМодель активнее выдумывает\nсинонимы и литературные\nфразы, но может исказить\nточный смысл текста.",
"help_topp":"🎯 ВЫБОРКА СЛОВ\n(top_p, 0.0 - 1.0)\n\nОграничивает диапазон слов,\nиз которых выбирает ИИ.\n\n• Меньше (0.1 - 0.3):\nОтсекает все сомнительные\nварианты, оставляя только\nсамые подходящие слова.\n\n• Больше (0.8 - 1.0):\nРазрешает редкие слова\nи необычные обороты.\n\nРекомендуется: 0.2",
"help_tokens":"📏 БУФЕР ОТВЕТА\n(max_tokens, 512 - 8192)\n\nМаксимальный объем текста,\nкоторый модель вернет.\n\n• 1 токен ≈ 3-4 буквы.\n\n• 2048 - 4096 токенов:\nГарантирует, что длинный\nабзац, диалог или статья\nпереведутся целиком и не\nоборвутся на полуслове.",
"help_thinking":"🧠 РАССУЖДЕНИЯ\n(Chain of Thought / CoT)\n\nРежим внутренних мыслей\nнейросети перед ответом.\n\n❌ ВЫКЛЮЧЕНО (стандарт):\n• Плюс: Перевод моментальный\n(всего 1-2 секунды).\n• Для обычного текста и игр\nразмышления не требуются.\n\n✅ ВКЛЮЧЕНО:\n• Плюс: Помогает при переводе\nсложных загадок и шифров.\n• Минус: Время отклика падает\nв 10-20 раз (до 20-30 сек).",
"help_glossary":"📚 УМНЫЙ ГЛОССАРИЙ (Словарь)\n\nКонтекстные подсказки терминов.\n\n• В исходный текст рядом с термином\nдописывается подсказка перевода.\n\n• Нейросеть берет этот перевод и\nСАМОСТОЯТЕЛЬНО согласует падеж,\nрод, число, время и окончания под\nграмматику всего предложения.\n\n• Исключает машинную топорную\nзамену и сохраняет живой язык.",
"help_close_hint":"* Кликните в любом месте, чтобы закрыть",

"menu_cut":"Вырезать",
"menu_copy":"Копировать",
"menu_paste":"Вставить",
"menu_select_all":"Выделить всё",

"btn_cancel":"Отмена",
"btn_save":"Сохранить",
"btn_close":"Закрыть",
"btn_delete":"Удалить",
"btn_browse":"Обзор...",

"confirm_delete_title":"Подтверждение удаления",
"confirm_delete_msg":"Вы действительно хотите полностью удалить сервис «{name}»?\n\nБудут безвозвратно удалены:\n• Файлы плагина в Хабе (data/services/{id})\n• Скрипт кнопки в QTranslate (Services/{id})\n• Персональные пресеты и настройки модели\n\nЭто действие нельзя отменить.",
"deleted_title":"Удалено",
"deleted_msg":"Сервис «{name}» и все его файлы успешно удалены.",

"tray_show":"Показать главное окно",
"tray_hide":"Скрыть в трей",
"tray_browser":"🌐 Открыть браузер",
"tray_ocr":"📸 Снимок экрана (OCR)",
"tray_tts":"🎙️ Озвучить буфер (TTS)",
"tray_lang":"Язык интерфейса",
"tray_exit":"Выход",

"theme_light":"Светлая",
"theme_dark":"Тёмная",
"theme_gray":"Серый",
"theme_nord":"Норд",
"theme_ochre":"Охра",
"font_small":"Компактный (8pt)",
"font_normal":"Стандартный (9pt)",
"font_large":"Увеличенный (11pt)",
"font_huge":"Крупный (13pt)"
},

"en":{
"__lang_name__":"English",
"app_title":"QTranslate AI Hub",
"services_title":"CONNECTED AI ENGINES & TRANSLATORS",
"add_service":"+ Add Service from Template",
"btn_browser":"Browser",
"tip_browser":"Open browser window",
"btn_ocr":"📸 OCR Snip",
"tip_ocr":"Screen capture OCR with direct transfer to QTranslate. Select area with mouse.",
"tip_ocr_settings":"OCR Settings",
"btn_dict":"📚 Dictionary",
"tip_dict":"Terminology dictionary & Smart Glossary",
"btn_batch":"📁 Batch Translation",
"tip_batch":"Batch file & mod translation",
"btn_settings":"⚙️ Settings",
"tip_settings":"Application Settings",

"status_ready":"Ready",
"status_not_ready":"Not Ready",
"tip_service_settings":"Service Parameters",
"tip_service_delete":"Delete service and all its files",
"tip_add_preset":"Create new preset",
"tip_edit_preset":"Edit active preset",
"tip_select_preset":"Select style: {name}",
"param_temp":"temperature",
"param_topp":"top_p",
"param_tokens":"max_tokens",
"param_thinking":"Reasoning",
"param_glossary":"Glossary",

"help_temp":"🌡️ TEMPERATURE\n(temperature, 0.0 - 1.0)\n\nControls translation strictness\nand predictability.\n\n• Lower (0.0 - 0.2):\nTranslation is highly accurate,\nstrict and literal.\nIdeal for UI, code and docs.\n\n• Higher (0.7 - 1.0):\nModel generates creative\nsynonyms and literary turns,\nbut may alter nuances.",
"help_topp":"🎯 WORD SAMPLING\n(top_p, 0.0 - 1.0)\n\nRestricts token candidate pool.\n\n• Lower (0.1 - 0.3):\nFilters out unlikely tokens,\nkeeping strictly relevant terms.\n\n• Higher (0.8 - 1.0):\nAllows rare words and diversity.\n\nRecommended: 0.2",
"help_tokens":"📏 RESPONSE BUFFER\n(max_tokens, 512 - 8192)\n\nMaximum response length\nreturned by model.\n\n• 1 token ≈ 3-4 chars.\n\n• 2048 - 4096 tokens:\nGuarantees full paragraphs,\ndialogues or books translate\nwithout mid-sentence cuts.",
"help_thinking":"🧠 REASONING (CoT)\n(Chain of Thought)\n\nInternal reflection process\nprior to translation.\n\n❌ OFF (Recommended):\n• Instant translation (1-2s).\n• Not needed for gaming/prose.\n\n✅ ON:\n• Helps with complex logic\nriddles and cryptograms.\n• Latency rises 10-20x (20-30s).",
"help_glossary":"📚 SMART GLOSSARY\n\nContextual terminology injection.\n\n• Hints are injected inline\nnext to matched source terms.\n\n• Neural model autonomously\ninflects case, gender, tense,\nand number for natural syntax.\n\n• Eliminates rigid string replacement.",
"help_close_hint":"* Click anywhere to dismiss",

"menu_cut":"Cut",
"menu_copy":"Copy",
"menu_paste":"Paste",
"menu_select_all":"Select All",

"btn_cancel":"Cancel",
"btn_save":"Save",
"btn_close":"Close",
"btn_delete":"Delete",
"btn_browse":"Browse...",

"confirm_delete_title":"Confirm Deletion",
"confirm_delete_msg":"Are you sure you want to permanently delete service «{name}»?\n\nThe following will be erased:\n• Hub plugin files (data/services/{id})\n• QTranslate script (Services/{id})\n• Model presets and settings\n\nThis action cannot be undone.",
"deleted_title":"Deleted",
"deleted_msg":"Service «{name}» and all its files were successfully deleted.",

"tray_show":"Show Main Window",
"tray_hide":"Hide to Tray",
"tray_browser":"🌐 Open Browser",
"tray_ocr":"📸 Screen Capture (OCR)",
"tray_tts":"🎙️ Speak Clipboard (TTS)",
"tray_lang":"Interface Language",
"tray_exit":"Exit",

"theme_light":"Light",
"theme_dark":"Dark",
"theme_gray":"Gray",
"theme_nord":"Nord",
"theme_ochre":"Ochre",
"font_small":"Compact (8pt)",
"font_normal":"Standard (9pt)",
"font_large":"Enlarged (11pt)",
"font_huge":"Large (13pt)"
},

"de":{
"__lang_name__":"Deutsch",
"app_title":"QTranslate AI Hub",
"services_title":"VERBUNDENE KI-DIENSTE & ÜBERSETZER",
"add_service":"+ Dienst aus Vorlage hinzufügen",
"btn_browser":"Browser",
"tip_browser":"Browserfenster öffnen",
"btn_ocr":"📸 OCR-Screenshot",
"tip_ocr":"Texterkennung vom Bildschirm mit direkter Übergabe an QTranslate. Bereich mit Maus wählen.",
"tip_ocr_settings":"OCR-Einstellungen",
"btn_dict":"📚 Wörterbuch",
"tip_dict":"Fachwörterbuch & Intelligentes Glossar",
"btn_batch":"📁 Stapelübersetzung",
"tip_batch":"Stapelübersetzung von Dateien und Mods",
"btn_settings":"⚙️ Einstellungen",
"tip_settings":"Programmeinstellungen",

"status_ready":"Bereit",
"status_not_ready":"Nicht bereit",
"tip_service_settings":"Dienstparameter",
"tip_service_delete":"Dienst und alle Dateien löschen",
"tip_add_preset":"Neue Voreinstellung erstellen",
"tip_edit_preset":"Aktive Voreinstellung bearbeiten",
"tip_select_preset":"Stil wählen: {name}",
"param_temp":"temperature",
"param_topp":"top_p",
"param_tokens":"max_tokens",
"param_thinking":"Überlegung",
"param_glossary":"Glossar",

"help_temp":"🌡️ TEMPERATUR\n(temperature, 0.0 - 1.0)\n\nSteuert Strenge und\nVorhersehbarkeit der Übersetzung.\n\n• Niedriger (0.0 - 0.2):\nPräzise, wortgetreu und strikt.\nIdeal für UI, Code und Dokumente.\n\n• Höher (0.7 - 1.0):\nKreativere Synonyme und literarischer\nAusdruck, kann Nuancen verändern.",
"help_topp":"🎯 WORTSAMPLING\n(top_p, 0.0 - 1.0)\n\nBegrenzt Wortauswahlpool der KI.\n\n• Niedriger (0.1 - 0.3):\nFiltert unwahrscheinliche Wörter,\nbehält strikt passende Begriffe.\n\n• Höher (0.8 - 1.0):\nErlaubt seltenere Wörter.\n\nEmpfohlen: 0.2",
"help_tokens":"📏 ANTWORTPUFFER\n(max_tokens, 512 - 8192)\n\nMaximale Ausgabelänge der KI.\n\n• 1 Token ≈ 3-4 Zeichen.\n\n• 2048 - 4096 Tokens:\nGarantiert vollständige Absätze,\nDialoge oder Bücher ohne Abbruch.",
"help_thinking":"🧠 GEDANKENGANG (CoT)\n(Chain of Thought)\n\nInterner Reflexionsprozess vor\nder Ausgabe.\n\n❌ AUS (Empfohlen):\n• Sofortige Übersetzung (1-2s).\n• Für Gaming/Prosa unnötig.\n\n✅ AN:\n• Hilft bei komplexer Logik.\n• Latenz steigt 10-20x (20-30s).",
"help_glossary":"📚 INTELLIGENTES GLOSSAR\n\nKontextuelle Begriffshinweise.\n\n• Hinweise werden direkt neben\nQuellbegriffen eingefügt.\n\n• KI passt Fälle, Geschlecht,\nNumerus und Endungen natürlich an.\n\n• Verhindert starres Ersetzen.",
"help_close_hint":"* Klicken zum Schließen",

"menu_cut":"Ausschneiden",
"menu_copy":"Kopieren",
"menu_paste":"Einfügen",
"menu_select_all":"Alles auswählen",

"btn_cancel":"Abbrechen",
"btn_save":"Speichern",
"btn_close":"Schließen",
"btn_delete":"Löschen",
"btn_browse":"Durchsuchen...",

"confirm_delete_title":"Löschen bestätigen",
"confirm_delete_msg":"Möchten Sie den Dienst «{name}» wirklich dauerhaft löschen?\n\nFolgendes wird gelöscht:\n• Hub-Plugin-Dateien (data/services/{id})\n• QTranslate-Skript (Services/{id})\n• Voreinstellungen und Einstellungen\n\nDies kann nicht rückgängig gemacht werden.",
"deleted_title":"Gelöscht",
"deleted_msg":"Dienst «{name}» und alle zugehörigen Dateien wurden erfolgreich gelöscht.",

"tray_show":"Hauptfenster anzeigen",
"tray_hide":"In Tray minimieren",
"tray_browser":"🌐 Browser öffnen",
"tray_ocr":"📸 Screenshot (OCR)",
"tray_tts":"🎙️ Zwischenablage vorlesen (TTS)",
"tray_lang":"Sprache",
"tray_exit":"Beenden",

"theme_light":"Hell",
"theme_dark":"Dunkel",
"theme_gray":"Grau",
"theme_nord":"Nord",
"theme_ochre":"Ocker",
"font_small":"Kompakt (8pt)",
"font_normal":"Standard (9pt)",
"font_large":"Vergrößert (11pt)",
"font_huge":"Groß (13pt)"
},

"fr":{
"__lang_name__":"Français",
"app_title":"QTranslate AI Hub",
"services_title":"MOTEURS D'IA ET TRADUCTEURS CONNECTÉS",
"add_service":"+ Ajouter un service depuis un modèle",
"btn_browser":"Navigateur",
"tip_browser":"Ouvrir la fenêtre du navigateur",
"btn_ocr":"📸 Capture OCR",
"tip_ocr":"Reconnaissance de texte à l'écran transmise à QTranslate. Sélectionnez la zone avec la souris.",
"tip_ocr_settings":"Paramètres OCR",
"btn_dict":"📚 Dictionnaire",
"tip_dict":"Dictionnaire terminologique et Glossaire intelligent",
"btn_batch":"📁 Traduction par lots",
"tip_batch":"Traduction par lots de fichiers et de mods",
"btn_settings":"⚙️ Paramètres",
"tip_settings":"Paramètres de l'application",

"status_ready":"Prêt",
"status_not_ready":"Pas prêt",
"tip_service_settings":"Paramètres du service",
"tip_service_delete":"Supprimer le service et tous ses fichiers",
"tip_add_preset":"Créer un nouveau préréglage",
"tip_edit_preset":"Modifier le préréglage actif",
"tip_select_preset":"Choisir le style : {name}",
"param_temp":"temperature",
"param_topp":"top_p",
"param_tokens":"max_tokens",
"param_thinking":"Raisonnement",
"param_glossary":"Glossaire",

"help_temp":"🌡️ TEMPÉRATURE\n(temperature, 0.0 - 1.0)\n\nContrôle la rigueur et la\nprévisibilité de la traduction.\n\n• Plus bas (0.0 - 0.2) :\nTraduction précise, stricte\net littérale. Idéal pour UI et code.\n\n• Plus haut (0.7 - 1.0) :\nSynonymes créatifs et style littéraire,\nmais peut altérer les nuances.",
"help_topp":"🎯 ÉCHANTILLONNAGE\n(top_p, 0.0 - 1.0)\n\nRestreint le choix des mots de l'IA.\n\n• Plus bas (0.1 - 0.3) :\nÉlimine les mots improbables,\ngarde les termes exacts.\n\n• Plus haut (0.8 - 1.0) :\nPermet des mots plus variés.\n\nRecommandé : 0.2",
"help_tokens":"📏 TAMPON DE RÉPONSE\n(max_tokens, 512 - 8192)\n\nLongueur maximale retournée par l'IA.\n\n• 1 jeton ≈ 3-4 caractères.\n\n• 2048 - 4096 jetons :\nGarantit des paragraphes entiers,\ndialogues ou livres sans coupure.",
"help_thinking":"🧠 RAISONNEMENT (CoT)\n(Chain of Thought)\n\nProcessus de réflexion interne\navant la réponse.\n\n❌ DÉSACTIVÉ (Recommandé) :\n• Traduction instantanée (1-2s).\n• Inutile pour les jeux et la prose.\n\n✅ ACTIVÉ :\n• Utile pour la logique complexe.\n• Délai accru 10-20x (20-30s).",
"help_glossary":"📚 GLOSSAIRE INTELLIGENT\n\nInjection terminologique contextuelle.\n\n• Indices injectés à côté des termes source.\n\n• L'IA accorde le genre, le nombre,\nle temps et la syntaxe naturellement.\n\n• Évite le remplacement mécanique rigide.",
"help_close_hint":"* Cliquez n'importe où pour fermer",

"menu_cut":"Couper",
"menu_copy":"Copier",
"menu_paste":"Coller",
"menu_select_all":"Tout sélectionner",

"btn_cancel":"Annuler",
"btn_save":"Enregistrer",
"btn_close":"Fermer",
"btn_delete":"Supprimer",
"btn_browse":"Parcourir...",

"confirm_delete_title":"Confirmer la suppression",
"confirm_delete_msg":"Voulez-vous vraiment supprimer définitivement le service «{name}» ?\n\nSeront supprimés :\n• Fichiers du plugin Hub (data/services/{id})\n• Script QTranslate (Services/{id})\n• Préréglages et paramètres du modèle\n\nCette action est irréversible.",
"deleted_title":"Supprimé",
"deleted_msg":"Le service «{name}» et tous ses fichiers ont été supprimés avec succès.",

"tray_show":"Afficher la fenêtre principale",
"tray_hide":"Réduire dans la zone de notification",
"tray_browser":"🌐 Ouvrir le navigateur",
"tray_ocr":"📸 Capture d'écran (OCR)",
"tray_tts":"🎙️ Lire le presse-papiers (TTS)",
"tray_lang":"Langue de l'interface",
"tray_exit":"Quitter",

"theme_light":"Clair",
"theme_dark":"Sombre",
"theme_gray":"Gris",
"theme_nord":"Nord",
"theme_ochre":"Ocre",
"font_small":"Compact (8pt)",
"font_normal":"Standard (9pt)",
"font_large":"Agrandie (11pt)",
"font_huge":"Grande (13pt)"
}
}

class I18nManager :
    def __init__ (self ):
        self .base_dir =get_base_dir ()
        self .locales_dir =os .path .join (self .base_dir ,"data","locales")
        self .current_lang ="ru"
        self .translations ={}
        self ._ensure_locale_files ()
        self .reload ()

    def _ensure_locale_files (self ):
        try :
            if not os .path .exists (self .locales_dir ):
                os .makedirs (self .locales_dir ,exist_ok =True )

            for lang_code ,data in DEFAULT_LOCALES .items ():
                file_path =os .path .join (self .locales_dir ,f"{lang_code }.json")
                if not os .path .exists (file_path ):
                    with open (file_path ,"w",encoding ="utf-8")as f :
                        json .dump (data ,f ,ensure_ascii =False ,indent =4 )
        except Exception :
            pass

    def get_available_languages (self ):
        langs =[("auto","Авто (Windows)")]
        discovered =set (DEFAULT_LOCALES .keys ())

        if os .path .exists (self .locales_dir ):
            for item in os .listdir (self .locales_dir ):
                if item .lower ().endswith (".json"):
                    code =item [:-5 ].lower ()
                    discovered .add (code )

        for code in sorted (discovered ):

            native_name =""
            json_path =os .path .join (self .locales_dir ,f"{code }.json")
            if os .path .exists (json_path ):
                try :
                    with open (json_path ,"r",encoding ="utf-8")as f :
                        data =json .load (f )
                        native_name =data .get ("__lang_name__","")
                except Exception :pass

            if not native_name :
                native_name =KNOWN_LANG_NAMES .get (code ,code .upper ())

            langs .append ((code ,native_name ))

        return langs

    def detect_windows_language (self ):
        try :
            lcid =ctypes .windll .kernel32 .GetUserDefaultUILanguage ()

            if lcid in (0x0419 ,0x0422 ,0x0423 ):
                return "ru"

            if (lcid &0xFF )==0x07 :
                return "de"

            if (lcid &0xFF )==0x0C :
                return "fr"

            if (lcid &0xFF )==0x0A :
                return "es"

            if (lcid &0xFF )==0x10 :
                return "it"

            if lcid ==0x0405 :
                return "cs"

            if lcid ==0x041F :
                return "tr"

            if (lcid &0xFF )==0x04 :
                return "zh"
            return "en"
        except Exception :
            return "ru"

    def reload (self ,lang_override =None ):
        if lang_override :
            chosen =lang_override
        else :
            try :
                from data .core .config_manager import config
                cfg_lang =config .get_str ("GENERAL","UILanguage","auto").lower ()
            except Exception :
                cfg_lang ="auto"

            if cfg_lang =="auto":
                chosen =self .detect_windows_language ()
            else :
                chosen =cfg_lang

        self .current_lang =chosen
        file_path =os .path .join (self .locales_dir ,f"{chosen }.json")

        loaded ={}
        if os .path .exists (file_path ):
            try :
                with open (file_path ,"r",encoding ="utf-8")as f :
                    loaded =json .load (f )
            except Exception :pass

        fallback_en =DEFAULT_LOCALES .get ("en",{})
        fallback_ru =DEFAULT_LOCALES .get ("ru",{})
        base_fallback =DEFAULT_LOCALES .get (chosen ,fallback_en )

        self .translations ={**fallback_ru ,**fallback_en ,**base_fallback ,**loaded }

    def t (self ,key ,default ="",**kwargs ):
        val =self .translations .get (key ,default or DEFAULT_LOCALES ["en"].get (key ,DEFAULT_LOCALES ["ru"].get (key ,key )))
        if kwargs :
            try :
                val =val .format (**kwargs )
            except Exception :pass
        return val

    def set_language (self ,lang_code ):
        clean_code =str (lang_code ).lower ().strip ()
        try :
            from data .core .config_manager import config
            config .set_value ("GENERAL","UILanguage",clean_code )
        except Exception :pass
        self .reload (lang_override =(None if clean_code =="auto"else clean_code ))

i18n =I18nManager ()
t =i18n .t
