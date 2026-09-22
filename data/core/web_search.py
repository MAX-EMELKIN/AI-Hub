# -*- coding: utf-8 -*-
# data/core/web_search.py

import html, re, json, ssl, time
import urllib.parse, urllib.request, urllib.error
from data.core.logger import logger
from data.core.i18n import i18n, t

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

DEFAULT_SEARCH_PROMPT = (
    "ИНСТРУМЕНТЫ ВЕБ-ПОИСКА:\n"
    "Тебе доступны инструменты `search_web` (мультипоиск в сети) и `fetch_webpage` (чтение ссылок).\n"
    "ПРАВИЛА ИСПОЛЬЗОВАНИЯ:\n"
    "1. Вызывай поиск ТОЛЬКО если в тексте есть конкретный неочевидный факт, точное имя или URL-ссылка.\n"
    "2. СТРОГИЙ ЛИМИТ: Разрешено делать НЕ БОЛЕЕ ОДНОГО (1) поискового запроса за весь ответ. Запрещено вызывать поиск повторно.\n"
    "3. Если поиск не дал результатов или вопрос понятен — сразу пиши перевод/ответ своими словами."
)

OPENAI_WEB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Поиск фактов в сети. ВНИМАНИЕ: Можно вызывать строго 1 раз за запрос! Повторные вызовы запрещены.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Точный поисковый запрос (например: 'QTranslate official website')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Чтение текстового содержимого веб-страницы по URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Полный веб-адрес (http:// или https://)"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

GEMINI_WEB_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "search_web",
                "description": "Поиск фактов в сети. СТРОГО 1 раз за запрос!",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "Точный поисковый запрос"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "fetch_webpage",
                "description": "Чтение текстового содержимого веб-страницы по URL.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {
                            "type": "STRING",
                            "description": "Полный веб-адрес"
                        }
                    },
                    "required": ["url"]
                }
            }
        ]
    }
]

GL_MAP = {
    "ru": "ru", "en": "us", "de": "de", "fr": "fr", "es": "es",
    "it": "it", "cs": "cz", "pl": "pl", "pt": "br", "tr": "tr",
    "ja": "jp", "ko": "kr", "zh": "cn", "zh-tw": "tw"
}

DDG_KL_MAP = {
    "ru": "ru-ru", "en": "us-en", "de": "de-de", "fr": "fr-fr", "es": "es-es",
    "it": "it-it", "cs": "cz-cs", "pl": "pl-pl", "pt": "br-pt", "tr": "tr-tr",
    "ja": "jp-jp", "ko": "kr-kr", "zh": "cn-zh", "zh-tw": "tw-tzh"
}

FALLBACK_SEARXNG_INSTANCES = [
    "https://search.sapti.me/search",
    "https://searx.tiekoetter.com/search",
    "https://northboot.xyz/search",
    "https://search.ononoki.org/search"
]

JS_CLICK_EXPAND_ONCE = """
(() => {
    let b = document.querySelector('div[jsname="rPRdsc"]') 
         || Array.from(document.querySelectorAll('div[role="button"], button')).find(el => (el.innerText || el.getAttribute('aria-label') || '').includes('Развернуть'));
    if (b) {
        b.click();
        return true;
    }
    return false;
})()
"""

JS_EXTRACT_CONTENT = """
(() => {
    let result = {
        "overview": "",
        "items": []
    };

    let t = (document.body.innerText || "").trim();
    let s = t.indexOf("Обзор от ИИ");
    if (s === -1) {
        s = t.indexOf("AI Overview");
    }

    if (s !== -1) {
        let p = t.slice(s);

        // Отсекаем нижний хвост со сниппетами и кнопками «Показать все»
        let endIdx = p.indexOf("\\nРезультаты поиска\\n");
        if (endIdx === -1) endIdx = p.indexOf("\\nПоказать все\\n\\n");
        if (endIdx === -1) endIdx = p.indexOf("\\nСсылки в нижнем колонтитуле");
        if (endIdx !== -1) p = p.slice(0, endIdx);

        // 1. Удаление заголовков и служебных плашек
        p = p.replace(/^(?:Обзор от ИИ|AI Overview)\\s*/i, "");
        p = p.replace(/\\nИспользуйте код с осторожностью\\s*/gi, "\\n");
        p = p.replace(/\\n(?:Загрузка…|Развернуть)\\s*$/gi, "");

        // 2. Очистка от мусорных плашек сносок вида (+1, +2, +3 и названий сайтов перед ними)
        p = p.replace(/\\n[^\\n]{2,45}\\n\\s*\\+[0-9]+\\s*(?=\\n|$)/g, "\\n");
        p = p.replace(/\\n\\s*\\+[0-9]+\\s*(?=\\n|$)/g, "\\n");
        p = p.replace(/\\s*\\+[0-9]+\\b/g, "");

        // 3. Удаление изолированных строк с названиями платформ-сносок, стоящих отдельно
        p = p.replace(/\\n(?:OpenClaw Docs|Cerebras|Docker Docs|Solo\\.io|Alibaba Cloud|LiteLLM|GitHub|OpenAI Developers|Agno Documentation|APIs\\.io|Medium|Baseten|vLLM)\\s*(?=\\n)/gi, "\\n");

        // 4. Отсечение блока карточек в самом конце (если остался хвост перед «Показать все»)
        let cardTail = p.search(/\\n(?:[A-Za-z0-9\\.\\-\\s]{2,30}\\n)?(?:Deploy model|List endpoints|Get Started|Chat Completions|Make your first API call)[\\s\\S]*$/i);
        if (cardTail !== -1 && cardTail > 400) {
            p = p.slice(0, cardTail).trim();
        }

        p = p.replace(/\\n{3,}/g, "\\n\\n");
        result.overview = p.trim();
    }

    // Собираем органические ссылки только если обзора от ИИ нет
    if (!result.overview) {
        let seenUrls = new Set();
        let rso = document.querySelector('div#rso') || document.querySelector('div#search') || document.querySelector('div[role="main"]');
        if (rso) {
            let blocks = rso.querySelectorAll('div.MjjYud, div.g, div.tF2Cxc');
            for (let b of blocks) {
                let h3 = b.querySelector('h3');
                let a = b.querySelector('a[href]');
                if (!h3 || !a) continue;

                let link = a.href;
                if (!link.startsWith('http') || link.includes('google.') || link.includes('gstatic.com') || link.includes('youtube.com')) {
                    continue;
                }
                if (seenUrls.has(link)) continue;

                let title = h3.innerText.trim();
                let snipEl = b.querySelector('div.VwiC3b, div[style*="-webkit-line-clamp"], span.aCOpRe, div.yXK7lf');
                let snippet = snipEl ? snipEl.innerText.trim() : "";

                if (title && title.length > 2) {
                    seenUrls.add(link);
                    result.items.push({
                        "title": title,
                        "url": link,
                        "snippet": snippet
                    });
                    if (result.items.length >= 4) break;
                }
            }
        }
    }

    return JSON.stringify(result);
})()
"""

def get_user_language():
    try:
        if hasattr(i18n, "current_lang") and i18n.current_lang:
            return i18n.current_lang.lower().strip()
    except Exception:
        pass
    try:
        from data.core.config_manager import config
        lang = config.get_str("GENERAL", "UILanguage", "auto").lower().strip()
        if lang and lang != "auto":
            return lang
    except Exception:
        pass
    return "ru"

def search_google_browser(query, max_results=4):
    clean_query = str(query).strip()
    if not clean_query:
        return t("search_query_empty", "Поисковый запрос пуст.")

    lang = get_user_language()
    gl = GL_MAP.get(lang, "ru")

    from data.core.cdp_client import browser_cdp
    browser_cdp.ensure_browser_running()

    params = {
        "q": clean_query,
        "hl": lang,
        "gl": gl
    }
    search_url = "https://www.google.com/search?" + urllib.parse.urlencode(params)
    browser_cdp.navigate_tab("google", search_url)

    data = {"overview": "", "items": []}
    expanded_clicked = False
    prev_len = 0
    stable_count = 0
    start_time = time.time()

    while time.time() - start_time < 12.0:
        time.sleep(0.5)
        raw_json = browser_cdp.evaluate_js_on_tab("google", JS_EXTRACT_CONTENT)
        if not raw_json or raw_json == '{"overview":"","items":[]}':
            continue

        try:
            parsed = json.loads(raw_json)
            curr_ov = parsed.get("overview", "")
            curr_it = parsed.get("items", [])

            if len(curr_ov) > len(data.get("overview", "")):
                data["overview"] = curr_ov
            if curr_it:
                data["items"] = curr_it

            if len(curr_ov) > 50 and not expanded_clicked:
                try:
                    res_clk = browser_cdp.evaluate_js_on_tab("google", JS_CLICK_EXPAND_ONCE)
                    if res_clk == "true" or res_clk is True:
                        expanded_clicked = True
                except Exception:
                    pass

            cur_l = len(curr_ov)
            if cur_l > 400:
                if cur_l == prev_len:
                    stable_count += 1
                    if stable_count >= 3:
                        break
                else:
                    stable_count = 0
                    prev_len = cur_l

            elif cur_l > 0 and (time.time() - start_time > 8.0):
                break
        except Exception:
            pass

    sections = []

    # 1. Если сформирован обзор от ИИ — выводим ТОЛЬКО его, без мусорных форумных ссылок
    if data.get("overview"):
        cleaned_ov = data["overview"].replace("Загрузка…", "").replace("Развернуть", "").strip()
        sections.append(f"[{t('google_ai_overview', 'Обзор от ИИ (Google Gemini)')}]:\n\n{cleaned_ov}")
    else:
        # 2. Только если обзора нет — отдаем аккуратные сниппеты поиска
        items = data.get("items", [])
        if items:
            link_title = t("search_sources", "Источники и документация")
            sections.append(f"[{link_title}]:")
            for i, it in enumerate(items[:max_results], 1):
                title = it.get("title", "Результат")
                snippet = it.get("snippet", "")
                link = it.get("url", "")
                item_str = f"{i}. {title}"
                if snippet:
                    item_str += f"\n   {snippet}"
                if link:
                    item_str += f"\n   {t('link_lbl', 'Ссылка')}: {link}"
                sections.append(item_str)

    if not sections:
        raise ValueError(t("search_no_results", f"По запросу «{clean_query}» ничего не найдено."))

    return "\n\n".join(sections)

def _clean_ddg_url(raw_url):
    clean = str(raw_url).replace("&amp;", "&")
    if "uddg=" in clean:
        m = re.search(r'uddg=([^&]+)', clean)
        if m:
            return urllib.parse.unquote(m.group(1))
    if clean.startswith("//"):
        return "https:" + clean
    return clean

def search_duckduckgo(query, max_results=3):
    clean_query = str(query).strip()
    if not clean_query:
        return t("search_query_empty", "Поисковый запрос пуст.")

    lang = get_user_language()
    kl_code = DDG_KL_MAP.get(lang, "ru-ru")

    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": clean_query, "kl": kl_code}).encode("utf-8")
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{lang},{lang};q=0.9,en;q=0.8"
        }

        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        links = re.findall(r'<a[^>]+class=[\'"]result-link[\'"][^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', content, flags=re.DOTALL | re.IGNORECASE)
        snippets = re.findall(r'<td[^>]+class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', content, flags=re.DOTALL | re.IGNORECASE)

        results = []
        count = min(len(links), len(snippets), max_results)
        for i in range(count):
            raw_url, raw_title = links[i]
            raw_snippet = snippets[i]

            title = html.unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()
            snippet = html.unescape(re.sub(r'<[^>]+>', '', raw_snippet)).strip()
            actual_url = _clean_ddg_url(raw_url)

            if snippet:
                results.append(f"{i + 1}. {title}\n   {snippet}\n   {t('link_lbl', 'Ссылка')}: {actual_url}")

        if results:
            hdr = t("search_res_ddg", f"Результаты поиска DuckDuckGo ({lang.upper()}):")
            return f"{hdr}\n\n" + "\n\n".join(results)
    except Exception:
        pass

    return t("search_no_results", f"По запросу «{clean_query}» ничего не найдено.")

def _parse_searxng_html(content, max_results):
    results = []
    articles = re.findall(r'<article[^>]+class="[^"]*result[^"]*"[^>]*>(.*?)</article>', content, flags=re.DOTALL | re.IGNORECASE)
    if not articles:
        articles = re.findall(r'<div[^>]+class="[^"]*result[^"]*"[^>]*>(.*?)</div>', content, flags=re.DOTALL | re.IGNORECASE)

    for i, block in enumerate(articles[:max_results]):
        title_match = re.search(r'<h[34][^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.DOTALL | re.IGNORECASE)
        snippet_match = re.search(r'<p[^>]+class="[^"]*content[^"]*"[^>]*>(.*?)</p>', block, flags=re.DOTALL | re.IGNORECASE)
        if not snippet_match:
            snippet_match = re.search(r'<p[^>]+class="[^"]*result-content[^"]*"[^>]*>(.*?)</p>', block, flags=re.DOTALL | re.IGNORECASE)

        if title_match:
            link = title_match.group(1).strip()
            title = html.unescape(re.sub(r'<[^>]+>', '', title_match.group(2))).strip()
            snippet = html.unescape(re.sub(r'<[^>]+>', '', snippet_match.group(1))).strip() if snippet_match else ""
            if snippet:
                results.append(f"{i + 1}. {title}\n   {snippet}\n   {t('link_lbl', 'Ссылка')}: {link}")

    return results

def _query_searxng_instance(endpoint, query, max_results, lang):
    ep = endpoint.strip()
    if not ep.endswith("/search") and not ep.endswith("/search/"):
        ep = ep.rstrip("/") + "/search"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    params_json = {"q": query, "format": "json", "categories": "general", "language": lang}
    url_json = f"{ep}?{urllib.parse.urlencode(params_json)}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        req_json = urllib.request.Request(url_json, headers=headers)
        with urllib.request.urlopen(req_json, context=ctx, timeout=4.0) as resp:
            raw = resp.read().decode("utf-8", errors="ignore").strip()
            if raw.startswith("{") or raw.startswith("["):
                data = json.loads(raw)
                items = data.get("results", [])
                results = []
                for i, it in enumerate(items[:max_results]):
                    title = html.unescape(it.get("title", "Результат"))
                    snippet = html.unescape(it.get("content", ""))
                    link = it.get("url", "")
                    if snippet:
                        results.append(f"{i + 1}. {title}\n   {snippet}\n   {t('link_lbl', 'Ссылка')}: {link}")
                if results:
                    return results
    except Exception:
        pass

    params_html = {"q": query, "categories": "general", "language": lang}
    url_html = f"{ep}?{urllib.parse.urlencode(params_html)}"
    req_html = urllib.request.Request(url_html, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req_html, context=ctx, timeout=5.0) as resp:
        html_content = resp.read().decode("utf-8", errors="ignore")

    results_html = _parse_searxng_html(html_content, max_results)
    if results_html:
        return results_html

    raise ValueError("Инстанс SearXNG не вернул данных.")

def search_searxng(query, endpoint=None, max_results=3):
    clean_query = str(query).strip()
    if not clean_query:
        return t("search_query_empty", "Поисковый запрос пуст.")

    lang = get_user_language()
    instances = []
    if endpoint and str(endpoint).strip():
        instances.append(endpoint.strip())
    instances.extend(FALLBACK_SEARXNG_INSTANCES)

    for inst in instances:
        try:
            results = _query_searxng_instance(inst, clean_query, max_results, lang)
            if results:
                host = urllib.parse.urlparse(inst).netloc
                return f"Результаты поиска SearXNG ({host}) [{lang.upper()}]:\n\n" + "\n\n".join(results)
        except Exception:
            continue

    raise ConnectionError("Публичные инстансы SearXNG временно недоступны.")

def search_brave(query, api_key, max_results=3):
    clean_query = str(query).strip()
    if not clean_query or not api_key:
        return "Не задан запрос или API-ключ Brave Search."

    params = {"q": clean_query, "count": max_results}
    url = f"https://api.search.brave.com/res/v1/web/search?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key.strip(),
        "User-Agent": "QTranslate-AI-Hub/2.0"
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    items = data.get("web", {}).get("results", [])
    results = []
    for i, it in enumerate(items[:max_results]):
        title = html.unescape(it.get("title", "Результат"))
        snippet = html.unescape(it.get("description", ""))
        link = it.get("url", "")
        if snippet:
            results.append(f"{i + 1}. {title}\n   {snippet}\n   Ссылка: {link}")

    if results:
        return f"Результаты поиска Brave:\n\n" + "\n\n".join(results)
    return f"По запросу «{clean_query}» в Brave ничего не найдено."

def search_tavily(query, api_key, max_results=3):
    clean_query = str(query).strip()
    if not clean_query or not api_key:
        return "Не задан запрос или API-ключ Tavily."

    url = "https://api.tavily.com/search"
    payload = json.dumps({
        "api_key": api_key.strip(),
        "query": clean_query,
        "max_results": max_results
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    items = data.get("results", [])
    results = []
    for i, it in enumerate(items[:max_results]):
        title = html.unescape(it.get("title", "Результат"))
        snippet = html.unescape(it.get("content", ""))
        link = it.get("url", "")
        if snippet:
            results.append(f"{i + 1}. {title}\n   {snippet}\n   Ссылка: {link}")

    if results:
        return f"Результаты поиска Tavily:\n\n" + "\n\n".join(results)
    return f"По запросу «{clean_query}» в Tavily ничего не найдено."

def search_serper(query, api_key, max_results=3):
    clean_query = str(query).strip()
    if not clean_query or not api_key:
        return "Не задан запрос или API-ключ Serper."

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": clean_query, "num": max_results}).encode("utf-8")
    headers = {
        "X-API-KEY": api_key.strip(),
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    items = data.get("organic", [])
    results = []
    for i, it in enumerate(items[:max_results]):
        title = html.unescape(it.get("title", "Результат"))
        snippet = html.unescape(it.get("snippet", ""))
        link = it.get("link", "")
        if snippet:
            results.append(f"{i + 1}. {title}\n   {snippet}\n   Ссылка: {link}")

    if results:
        return f"Результаты поиска Serper (Google):\n\n" + "\n\n".join(results)
    return f"По запросу «{clean_query}» в Serper ничего не найдено."

def search_web(query, engine=None, max_results=4):
    from data.core.config_manager import config
    active_engine = (engine or config.get_str("SEARCH", "engine", "google")).lower().strip()

    t_start = time.time()
    res_text = ""
    try:
        if active_engine in ("google", "google_browser"):
            res_text = search_google_browser(query, max_results=max_results)
        elif active_engine == "searxng":
            endpoint = config.get_str("SEARCH", "searxng_url", "https://search.sapti.me/search")
            res_text = search_searxng(query, endpoint=endpoint, max_results=max_results)
        elif active_engine == "brave":
            key = config.get_str("SEARCH", "brave_key", "")
            res_text = search_brave(query, api_key=key, max_results=max_results)
        elif active_engine == "tavily":
            key = config.get_str("SEARCH", "tavily_key", "")
            res_text = search_tavily(query, api_key=key, max_results=max_results)
        elif active_engine == "serper":
            key = config.get_str("SEARCH", "serper_key", "")
            res_text = search_serper(query, api_key=key, max_results=max_results)
        else:
            res_text = search_duckduckgo(query, max_results=max_results)
    except Exception as e:
        ddg_res = search_duckduckgo(query, max_results=max_results)
        res_text = f"[{active_engine.upper()}: сбой ({e}). Резерв DuckDuckGo]:\n\n{ddg_res}"

    elapsed = round(time.time() - t_start, 2)
    logger.tool_call("WebSearch", 1, f"search_web ({active_engine}) [{elapsed}с]", {"query": query}, res_text[:400])

    return res_text

def fetch_webpage(url, max_chars=3000):
    clean_url = str(url).strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    lang = get_user_language()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": f"{lang},{lang};q=0.9,en;q=0.8"
    }

    t_start = time.time()
    try:
        req = urllib.request.Request(clean_url, headers=headers)
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        content = re.sub(r'<script[\s\S]*?</script>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<style[\s\S]*?</style>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<nav[\s\S]*?</nav>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<footer[\s\S]*?</footer>', '', content, flags=re.IGNORECASE)

        content = re.sub(r'<(?:br|p|div|li|h[1-6])[^>]*>', '\n', content, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', content)
        text = html.unescape(text)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        if len(clean_text) > max_chars:
            clean_text = clean_text[:max_chars] + "\n...[текст обрезан]"

        res_final = f"Содержимое страницы ({clean_url}):\n\n{clean_text}" if clean_text else "Страница пуста."
        elapsed = round(time.time() - t_start, 2)
        logger.tool_call("WebSearch", 1, f"fetch_webpage [{elapsed}с]", {"url": clean_url}, res_final[:400])
        return res_final

    except Exception as e:
        err_msg = f"Не удалось прочитать страницу {clean_url}: {e}"
        logger.tool_call("WebSearch", 1, "fetch_webpage [Error]", {"url": clean_url}, err_msg)
        return err_msg

def execute_tool_call(tool_name, tool_args):
    t_name = str(tool_name).lower().strip()

    if "search" in t_name:
        query = tool_args.get("query") or tool_args.get("q") or ""
        return search_web(query)
    elif "fetch" in t_name or "url" in t_name or "page" in t_name:
        target_url = tool_args.get("url") or tool_args.get("link") or ""
        return fetch_webpage(target_url)
    else:
        return f"Неизвестный инструмент: {tool_name}"