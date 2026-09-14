// =============================================================================
// Сервис: Google AI Mode (AI Hub Bridge)
// ID: 675
// =============================================================================

var LOCAL_URL    = "http://127.0.0.1:8080";
var SERVICE_ID   = 675;
var SERVICE_NAME = "Google AI (Browser)";

function serviceHeader() {
    return new ServiceHeader(
        SERVICE_ID,
        SERVICE_NAME,
        "Google Search AI Mode via Supermium / AI Hub" + Const.NL2 + LOCAL_URL,
        Capability.TRANSLATE
    );
}

function serviceHost(from, to, text) {
    return LOCAL_URL;
}

function serviceLink(text, from, to) {
    return "https://www.google.com/";
}

SupportedLanguages = [
    -1, "auto", "af", "az", "sq", "ar", "hy", "eu", "be", "bg", "ca", "zh-CN", "zh-TW",
    "hr", "cs", "da", "nl", "en", "et", "fi", "tl", "fr", "gl", "de", "el", "ht",
    "iw", "hi", "hu", "is", "id", "it", "ga", "ja", "ka", "ko", "lv", "lt", "mk",
    "ms", "mt", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw",
    "sv", "th", "tr", "uk", "ur", "vi", "cy", "yi", "eo", "hmn", "la", "lo", "kk",
    "uz", "si", "tg", "te", "km", "mn", "kn", "ta", "mr", "bn", "tt"
];

function serviceTranslateRequest(text, from, to) {
    try {
        text = limitSource(prepareLinkedSource(text), 4000);
        var sCode = codeFromLanguage(from);
        var tCode = codeFromLanguage(to);

        var payload = {
            text: text,
            from: (sCode && sCode !== UNKNOWN_LANGUAGE_CODE && sCode !== "auto") ? sCode : "auto",
            to: (tCode && tCode !== UNKNOWN_LANGUAGE_CODE && tCode !== "auto") ? tCode : "ru"
        };

        var headers = "Content-Type: application/json";
        return new RequestData(HttpMethod.POST, "/google_ai", stringifyJSON(payload), headers, CodePage.UTF8);
    } catch (e) {
        return new RequestData(HttpMethod.UNDEFINED, "", "");
    }
}

function serviceTranslateResponse(original, json, from, to) {
    try {
        if (!json) return new ResponseData(original + Const.NL2 + "[Google AI: Сервер AI Hub не ответил]", from, to);
        var data = parseJSON(json);
        if (!data) return new ResponseData(original + Const.NL2 + "[Ошибка парсера JSON]", from, to);
        if (data.error) return new ResponseData(original + Const.NL2 + "[Ошибка Google AI: " + data.error + "]", from, to);

        var result = trimString(String(data.response || ""));
        return new ResponseData(result, from, to);
    } catch (e) {
        return new ResponseData(original + Const.NL2 + "[Ошибка: " + (e.message || e) + "]", from, to);
    }
}