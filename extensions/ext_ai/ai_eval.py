"""
ai_eval.py — AI 风格评估模块
==============================
对 LUT 处理后的图像进行色彩统计，通过 OpenAI API 评估风格并排名
"""

import os, sys, math, json, time, hashlib
from typing import Optional, List, Dict, Tuple, Callable
from dataclasses import dataclass, asdict

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ============================================================
#  配置
# ============================================================
DEFAULT_API_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"

def get_api_config() -> Tuple[str, str, str]:
    return (
        os.environ.get("OPENAI_API_KEY", "").strip(),
        os.environ.get("OPENAI_BASE_URL", DEFAULT_API_URL).strip().rstrip("/"),
        os.environ.get("OPENAI_MODEL", DEFAULT_MODEL).strip(),
    )


# ============================================================
#  数据结构
# ============================================================
@dataclass
class ColorStats:
    name: str
    avg_r: float; avg_g: float; avg_b: float
    avg_h: float; avg_s: float; avg_v: float
    contrast: float; warm_bias: float

@dataclass
class EvalResult:
    name: str
    score: float
    style_tags: List[str]
    description: str
    analysis: str
    rank: int = 0


# ============================================================
#  色彩统计
# ============================================================
def extract_stats(img: 'Image', name: str = "") -> Optional[ColorStats]:
    if not HAS_PIL: return None
    img = img.convert("RGB")
    px = img.load()
    w, h = img.size
    n = w * h
    if not n: return None

    r_sum = g_sum = b_sum = 0.0
    h_sum = s_sum = v_sum = 0.0
    lum_vals = []

    for y in range(h):
        for x in range(w):
            pr, pg, pb = px[x, y]
            r_sum += pr; g_sum += pg; b_sum += pb
            mx, mn = max(pr, pg, pb), min(pr, pg, pb)
            vr = mx / 255.0
            sr = (mx - mn) / mx if mx else 0.0

            hue = 0.0
            if mx != mn:
                if mx == pr: hue = 60.0 * ((pg - pb) / (mx - mn))
                elif mx == pg: hue = 60.0 * (2.0 + (pb - pr) / (mx - mn))
                else: hue = 60.0 * (4.0 + (pr - pg) / (mx - mn))
            if hue < 0: hue += 360.0

            h_sum += hue
            s_sum += sr * 100.0
            v_sum += vr * 100.0
            lum_vals.append(0.299*pr + 0.587*pg + 0.114*pb)

    avg_lum = sum(lum_vals) / n
    contrast = math.sqrt(sum((x - avg_lum) ** 2 for x in lum_vals) / n)
    warm = (r_sum/n - b_sum/n) * (1.0 + s_sum/n/200.0)

    return ColorStats(
        name=name,
        avg_r=r_sum/n, avg_g=g_sum/n, avg_b=b_sum/n,
        avg_h=h_sum/n, avg_s=s_sum/n, avg_v=v_sum/n,
        contrast=contrast, warm_bias=warm)


def stats_to_text(stats: ColorStats) -> str:
    lines = [
        f"  RGB({stats.avg_r:.0f},{stats.avg_g:.0f},{stats.avg_b:.0f})"
        f" H:{stats.avg_h:.0f} S:{stats.avg_s:.1f}% V:{stats.avg_v:.1f}%"
        f" Contrast:{stats.contrast:.1f} Warm:{stats.warm_bias:.1f}"
    ]
    if stats.warm_bias > 5: lines.append("  → warm")
    elif stats.warm_bias < -5: lines.append("  → cool")
    return "\n".join(lines)


# ============================================================
#  API 调用
# ============================================================
def call_api(
    api_key: str, messages: list, model=DEFAULT_MODEL,
    base_url=DEFAULT_API_URL, max_tokens=4096, temp=0.3,
) -> Optional[str]:
    if not HAS_REQUESTS: return None
    try:
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temp},
            timeout=120)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return None
    except Exception:
        return None


def stream_api(
    api_key: str, messages: list, model=DEFAULT_MODEL,
    base_url=DEFAULT_API_URL, max_tokens=4096, temp=0.3,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    if not HAS_REQUESTS: return None
    full = ""
    try:
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temp, "stream": True},
            stream=True, timeout=120)
        if r.status_code != 200: return None
        for line in r.iter_lines():
            if not line: continue
            raw = line.decode("utf-8", errors="replace").strip()
            if not raw.startswith("data: "): continue
            d = raw[6:]
            if d == "[DONE]": break
            try:
                obj = json.loads(d)
                c = obj["choices"][0]["delta"].get("content", "")
                if c:
                    full += c
                    if on_chunk: on_chunk(c)
            except (json.JSONDecodeError, KeyError): continue
    except Exception:
        return None
    return full


# ============================================================
#  AI 评估
# ============================================================
_LANG = "en"

def set_lang(lang):
    global _LANG
    if lang in ("zh", "en"):
        _LANG = lang


def _lang_inst():
    """返回 AI 语言指令"""
    return "用中文回复，标签用中英文混合。风格标签用中文。" if _LANG == "zh" \
        else "Reply in English. Style tags in English."


def build_eval_prompt(stats_list: List[Tuple[str, str]]) -> str:
    items = []
    for i, (name, text) in enumerate(stats_list, 1):
        items.append(f"[{i}] {name}\n{text}")
    all_text = "\n\n".join(items)

    ai_lang = _lang_inst()
    return f"""You are a professional colorist. Analyze these LUT results:

{all_text}

{ai_lang}

Output strict JSON:
```json
{{
  "rankings": [
    {{
      "name": "LUT name",
      "rank": 1,
      "score": 92,
      "style_tags": ["温暖", "复古", "电影感"],
      "description": "one-line summary in language",
      "analysis": "100-200 word analysis based on color data"
    }}
  ],
  "best_lut": "top LUT name",
  "best_reason": "why this LUT fits best"
}}
```
score 0-100, 3-6 style tags, output only JSON."""


def build_query_prompt(results: List[EvalResult], query: str) -> str:
    items = []
    for r in results:
        items.append(
            f"[{r.name}] score:{r.score} tags:{','.join(r.style_tags)}\n"
            f"  desc: {r.description}\n  analysis: {r.analysis[:150]}")
    ai_lang = _lang_inst()
    return f"""You are a LUT recommendation expert.
Available LUTs:
{"\n".join(items)}

User wants: "{query}"
{ai_lang}
Recommend top 3 matches in JSON:
```json
{{
  "matches": [
    {{"name": "LUT", "relevance": 95, "reason": "why (50-100 words)"}}
  ]
}}
```"""


def parse_json(text: str) -> Dict:
    if not text: return {}
    import re
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    m = re.search(r'(\{.*\})', text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except json.JSONDecodeError: pass
    return {}


def evaluate(
    stats_list: List[Tuple[str, ColorStats]],
    api_key: str, model=DEFAULT_MODEL, base_url=DEFAULT_API_URL,
    stream_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[List[EvalResult], str, str]:
    items = [(name, stats_to_text(s)) for name, s in stats_list]
    prompt = build_eval_prompt(items)
    msgs = [
        {"role": "system", "content": "professional colorist"},
        {"role": "user", "content": prompt}]

    fn = stream_api if stream_cb else call_api
    resp = fn(api_key, msgs, model, base_url) if not stream_cb else \
           stream_api(api_key, msgs, model, base_url, on_chunk=stream_cb)
    parsed = parse_json(resp)

    results = []
    for r in parsed.get("rankings", []):
        results.append(EvalResult(
            name=r.get("name", ""), score=r.get("score", 50),
            style_tags=r.get("style_tags", []),
            description=r.get("description", ""),
            analysis=r.get("analysis", ""), rank=r.get("rank", 99)))
    results.sort(key=lambda x: x.rank)
    for i, r in enumerate(results): r.rank = i + 1
    return results, parsed.get("best_lut", ""), parsed.get("best_reason", "")


def query_match(
    results: List[EvalResult], query: str,
    api_key: str, model=DEFAULT_MODEL, base_url=DEFAULT_API_URL,
    stream_cb: Optional[Callable[[str], None]] = None,
) -> List[Dict]:
    if not results or not query: return []
    prompt = build_query_prompt(results, query)
    msgs = [
        {"role": "system", "content": "LUT recommendation expert"},
        {"role": "user", "content": prompt}]

    fn = stream_api if stream_cb else call_api
    resp = fn(api_key, msgs, model, base_url) if not stream_cb else \
           stream_api(api_key, msgs, model, base_url, on_chunk=stream_cb)
    return parse_json(resp).get("matches", [])


def local_evaluate(stats_list: List[Tuple[str, ColorStats]]) -> List[EvalResult]:
    """无 API 时本地统计评估"""
    results = []
    for name, s in stats_list:
        intensity = abs(s.avg_s - 28) * 0.3 + s.contrast * 0.1 + abs(s.warm_bias) * 0.15
        score = min(95, max(30, 50 + intensity))
        tags = []
        if s.warm_bias > 10: tags.append("warm")
        elif s.warm_bias < -10: tags.append("cool")
        else: tags.append("neutral")
        if s.avg_s > 45: tags.append("high_sat")
        elif s.avg_s < 20: tags.append("low_sat")
        if s.contrast > 60: tags.append("high_contrast")
        elif s.contrast < 30: tags.append("soft")
        results.append(EvalResult(
            name=name, score=score, style_tags=tags,
            description=f"Avg({s.avg_r:.0f},{s.avg_g:.0f},{s.avg_b:.0f}) S:{s.avg_s:.0f}%",
            analysis=f"Local analysis: contrast={s.contrast:.1f} warm={s.warm_bias:.1f}"))
    results.sort(key=lambda x: x.score, reverse=True)
    for i, r in enumerate(results): r.rank = i + 1
    return results
