// =============================================================================
// Сервис: Qwen Plus (Alibaba DashScope)
// ID: 706
// =============================================================================

var LOCAL_URL    = "http://127.0.0.1:8080";
var SERVICE_ID   = 706;
var SERVICE_NAME = "Qwen Plus";
var _IS_ALIVE    = false;

function serviceHeader() {
    return new ServiceHeader(
        SERVICE_ID,
        SERVICE_NAME,
        "Qwen Plus (Alibaba DashScope) via QTranslate AI Hub" + Const.NL2 + LOCAL_URL,
        Capability.TRANSLATE
    );
}

function serviceHost(from, to, text) {
    return LOCAL_URL;
}

function serviceLink(text, from, to) {
    return "https://dashscope.console.aliyun.com/";
}

SupportedLanguages = [
    -1, "auto", "af", "az", "sq", "ar", "hy", "eu", "be", "bg", "ca", "zh-CN", "zh-TW",
    "hr", "cs", "da", "nl", "en", "et", "fi", "tl", "fr", "gl", "de", "el", "ht",
    "iw", "hi", "hu", "is", "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk",
    "ms", "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw",
    "sv", "th", "tr", "uk", "ur", "vi", "cy", "yi", "eo", "hmn", "la", "lo", "kk",
    "uz", "si", "tg", "te", "km", "mn", "kn", "ta", "mr", "bn", "tt"
];

function _checkHubFast() {
    try {
        var h = new ActiveXObject("MSXML2.ServerXMLHTTP.6.0");
        h.open("OPTIONS", LOCAL_URL, false);
        h.setTimeouts(150, 150, 150, 150);
        h.send();
        return (h.status === 200 || h.status === 405 || h.status === 204);
    } catch (e) {
        try {
            var h2 = new ActiveXObject("WinHttp.WinHttpRequest.5.1");
            h2.Open("OPTIONS", LOCAL_URL, false);
            h2.SetTimeouts(150, 150, 150, 150);
            h2.Send();
            return (h2.Status === 200 || h2.Status === 405 || h2.Status === 204);
        } catch(e2) { return false; }
    }
}

function _ensureHub() {
    if (_IS_ALIVE || _checkHubFast()) { _IS_ALIVE = true; return true; }
    try {
        var sh = new ActiveXObject("WScript.Shell"), fso = new ActiveXObject("Scripting.FileSystemObject"), p = "";
        try {
            var wmi = GetObject("winmgmts:{impersonationLevel=impersonate}!\\\\.\\root\\cimv2");
            var procs = wmi.ExecQuery("Select ExecutablePath from Win32_Process Where Name = 'QTranslate.exe'");
            var it = new Enumerator(procs);
            if (!it.atEnd() && it.item().ExecutablePath) p = fso.BuildPath(fso.GetParentFolderName(it.item().ExecutablePath), "AI_Hub.exe");
        } catch(e) {}
        if (!p || !fso.FileExists(p)) {
            var c = [fso.BuildPath(sh.CurrentDirectory || "", "AI_Hub.exe"), "AI_Hub.exe", "..\\AI_Hub.exe", ".\\AI_Hub.exe"];
            for (var i = 0; i < c.length; i++) if (fso.FileExists(c[i])) { p = fso.GetAbsolutePathName(c[i]); break; }
        }
        if (p && fso.FileExists(p)) {
            sh.CurrentDirectory = fso.GetParentFolderName(p);
            sh.Run('"' + p + '"', 1, false);
            for (var a = 0; a < 25; a++) {
                sh.Run("ping 127.0.0.1 -n 1 -w 250 > nul", 0, true);
                if (_checkHubFast()) { _IS_ALIVE = true; return true; }
            }
        }
    } catch (e) {}
    _IS_ALIVE = _checkHubFast();
    return _IS_ALIVE;
}

function serviceTranslateRequest(text, from, to) {
    try {
        _ensureHub();
        text = limitSource(prepareLinkedSource(text), 4000);
        var sCode = codeFromLanguage(from);
        var tCode = codeFromLanguage(to);

        var payload = {
            text: text,
            from: (sCode && sCode !== UNKNOWN_LANGUAGE_CODE && sCode !== "auto") ? sCode : "auto",
            to: (tCode && tCode !== UNKNOWN_LANGUAGE_CODE && tCode !== "auto") ? tCode : "ru"
        };

        var headers = "Content-Type: application/json";
        return new RequestData(HttpMethod.POST, "/qwen_plus", stringifyJSON(payload), headers, CodePage.UTF8);
    } catch (e) {
        return new RequestData(HttpMethod.UNDEFINED, "", "");
    }
}

function serviceTranslateResponse(original, json, from, to) {
    try {
        if (!json) return new ResponseData(original + Const.NL2 + "[AI Hub: Сервер не ответил]", from, to);
        var data = parseJSON(json);
        if (!data) return new ResponseData(original + Const.NL2 + "[Ошибка парсера JSON]", from, to);
        if (data.error) return new ResponseData(original + Const.NL2 + "[Ошибка: " + data.error + "]", from, to);

        var result = trimString(String(data.response || ""));
        return new ResponseData(result, from, to);
    } catch (e) {
        return new ResponseData(original + Const.NL2 + "[Ошибка: " + (e.message || e) + "]", from, to);
    }
}