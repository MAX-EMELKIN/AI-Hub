# -*- coding: utf-8 -*-
# data/core/web_search.py

import html, re
import urllib.parse
import urllib.request
import urllib.error
USER_AGENT ="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

DEFAULT_SEARCH_PROMPT =(
"ИНСТРУМЕНТЫ ВЕБ-ПОИСКА:\n"
"Тебе доступны инструменты `search_web` (поиск в DuckDuckGo) и `fetch_webpage` (чтение ссылок).\n"
"ПРАВИЛА ИСПОЛЬЗОВАНИЯ:\n"
"1. Вызывай поиск ТОЛЬКО если в тексте есть конкретный неочевидный факт, точное имя или URL-ссылка.\n"
"2. СТРОГИЙ ЛИМИТ: Разрешено делать НЕ БОЛЕЕ ОДНОГО (1) поискового запроса за весь ответ. Запрещено вызывать поиск повторно.\n"
"3. Если поиск не дал результатов или вопрос понятен — сразу пиши перевод/ответ своими словами."
)

OPENAI_WEB_TOOLS =[
{
"type":"function",
"function":{
"name":"search_web",
"description":"Поиск фактов в DuckDuckGo. ВНИМАНИЕ: Можно вызывать строго 1 раз за запрос! Повторные вызовы запрещены.",
"parameters":{
"type":"object",
"properties":{
"query":{
"type":"string",
"description":"Точный поисковый запрос (например: 'Fallout season 2 release date')"
}
},
"required":["query"]
}
}
},
{
"type":"function",
"function":{
"name":"fetch_webpage",
"description":"Чтение текстового содержимого веб-страницы по URL.",
"parameters":{
"type":"object",
"properties":{
"url":{
"type":"string",
"description":"Полный веб-адрес (http:// или https://)"
}
},
"required":["url"]
}
}
}
]

GEMINI_WEB_TOOLS =[
{
"functionDeclarations":[
{
"name":"search_web",
"description":"Поиск фактов в DuckDuckGo. СТРОГО 1 раз за запрос!",
"parameters":{
"type":"OBJECT",
"properties":{
"query":{
"type":"STRING",
"description":"Точный поисковый запрос"
}
},
"required":["query"]
}
},
{
"name":"fetch_webpage",
"description":"Чтение текстового содержимого веб-страницы по URL.",
"parameters":{
"type":"OBJECT",
"properties":{
"url":{
"type":"STRING",
"description":"Полный веб-адрес"
}
},
"required":["url"]
}
}
]
}
]

def search_duckduckgo (query ,max_results =3 ):
    clean_query =str (query ).strip ()
    if not clean_query :
        return "Поисковый запрос пуст."

    url =f"https://html.duckduckgo.com/html/?q={urllib .parse .quote (clean_query )}"
    headers ={
    "User-Agent":USER_AGENT ,
    "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":"ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try :
        req =urllib .request .Request (url ,headers =headers )
        with urllib .request .urlopen (req ,timeout =5.0 )as resp :
            content =resp .read ().decode ("utf-8",errors ="ignore")

        title_matches =re .findall (r'<a[^>]+class="result__a"[^>]*>(.*?)</a>',content ,flags =re .DOTALL )
        snippet_matches =re .findall (r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',content ,flags =re .DOTALL )
        url_matches =re .findall (r'<a[^>]+class="result__url"[^>]*href="([^"]+)"',content ,flags =re .DOTALL )

        results =[]
        count =min (len (snippet_matches ),max_results )
        for i in range (count ):
            raw_title =title_matches [i ]if i <len (title_matches )else "Результат"
            raw_snippet =snippet_matches [i ]if i <len (snippet_matches )else ""
            raw_link =url_matches [i ]if i <len (url_matches )else ""

            title =re .sub (r'<[^>]+>','',raw_title ).strip ()
            title =html .unescape (title )
            snippet =re .sub (r'<[^>]+>','',raw_snippet ).strip ()
            snippet =html .unescape (snippet )

            if snippet :
                item_text =f"{i +1 }. {title }\n   {snippet }"
                if raw_link :
                    item_text +=f"\n   Ссылка: {raw_link }"
                results .append (item_text )

        if results :
            return f"Результаты поиска DuckDuckGo по запросу «{clean_query }»:\n\n"+"\n\n".join (results )
        return f"По запросу «{clean_query }» ничего не найдено. Прекрати поиски и отвечай своими словами."

    except Exception as e :
        return f"Ошибка поиска: {e }. Прекрати поиски."

def fetch_webpage (url ,max_chars =3000 ):
    clean_url =str (url ).strip ()
    if not clean_url .startswith ("http://")and not clean_url .startswith ("https://"):
        clean_url ="https://"+clean_url

    headers ={
    "User-Agent":USER_AGENT ,
    "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":"ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try :
        req =urllib .request .Request (clean_url ,headers =headers )
        with urllib .request .urlopen (req ,timeout =6.0 )as resp :
            content =resp .read ().decode ("utf-8",errors ="ignore")

        content =re .sub (r'<script[\s\S]*?</script>','',content ,flags =re .IGNORECASE )
        content =re .sub (r'<style[\s\S]*?</style>','',content ,flags =re .IGNORECASE )
        content =re .sub (r'<nav[\s\S]*?</nav>','',content ,flags =re .IGNORECASE )
        content =re .sub (r'<footer[\s\S]*?</footer>','',content ,flags =re .IGNORECASE )

        content =re .sub (r'<(?:br|p|div|li|h[1-6])[^>]*>','\n',content ,flags =re .IGNORECASE )
        text =re .sub (r'<[^>]+>','',content )
        text =html .unescape (text )

        lines =[line .strip ()for line in text .splitlines ()if line .strip ()]
        clean_text ="\n".join (lines )

        if len (clean_text )>max_chars :
            clean_text =clean_text [:max_chars ]+"\n...[текст обрезан]"

        return f"Содержимое страницы ({clean_url }):\n\n{clean_text }"if clean_text else "Страница пуста."

    except Exception as e :
        return f"Не удалось прочитать страницу {clean_url }: {e }"

def execute_tool_call (tool_name ,tool_args ):
    t_name =str (tool_name ).lower ().strip ()

    if "search"in t_name :
        query =tool_args .get ("query")or tool_args .get ("q")or ""
        print (f"  🔍 [Агентный поиск]: «{query }»")
        return search_duckduckgo (query )
    elif "fetch"in t_name or "url"in t_name or "page"in t_name :
        target_url =tool_args .get ("url")or tool_args .get ("link")or ""
        print (f"  🌐 [Чтение ссылки]: {target_url }")
        return fetch_webpage (target_url )
    else :
        return f"Неизвестный инструмент: {tool_name }"
