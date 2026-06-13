"""
lang.py — Internationalization module for klut.

Usage:
    from lang import tr, LANG
    LANG.set("en")  # or LANG.set("zh")
    label = tr("open_image")
"""


class _Lang:
    """Language manager."""

    def __init__(self):
        self._lang = "zh"

    def set(self, lang: str):
        if lang in ("zh", "en"):
            self._lang = lang

    def get(self) -> str:
        return self._lang


LANG = _Lang()


def tr(key: str) -> str:
    """Translate a key to the current language."""
    entry = _strings.get(key)
    if entry:
        return entry.get(LANG.get(), entry.get("en", key))
    return key


def ext_tr(table: dict, key: str) -> str:
    """Translate a key using an extension-provided string table.

    Extension string tables use the same { lang: text } dict format.
    """
    entry = table.get(key)
    if entry:
        return entry.get(LANG.get(), entry.get("en", key))
    return key


# ---------------------------------------------------------------------------
#  String table
# ---------------------------------------------------------------------------

_strings = {

    # Window
    "app_title": {"zh": "klut", "en": "klut"},

    # Menu
    "file_menu": {"zh": "文件", "en": "File"},
    "open_image": {"zh": "打开图片...", "en": "Open Image..."},
    "open_lut_files": {"zh": "打开 LUT 文件...", "en": "Open LUT Files..."},
    "export_png": {"zh": "导出 PNG...", "en": "Export PNG..."},
    "quit": {"zh": "退出", "en": "Quit"},
    "view_menu": {"zh": "视图", "en": "View"},
    "toggle_watermark": {"zh": "水印开关", "en": "Toggle Watermark"},
    "toggle_debug": {"zh": "调试面板", "en": "Toggle Debug"},
    "color_menu": {"zh": "色彩空间", "en": "ColorSpace"},
    "cycle_src_cs": {"zh": "切换源色彩空间", "en": "Cycle Source CS"},
    "cycle_lut_cs": {"zh": "切换 LUT 色彩空间", "en": "Cycle LUT CS"},

    # Toolbar
    "open": {"zh": "打开图片", "en": "Open"},
    "luts": {"zh": "选择 LUT", "en": "LUTs"},
    "export": {"zh": "导出", "en": "Export"},
    "wm": {"zh": "水印", "en": "WM"},
    "debug": {"zh": "调试", "en": "Debug"},
    "preview_limit": {"zh": "预览限制:", "en": "Preview limit:"},

    # Preview
    "original": {"zh": "原始", "en": "Original"},
    "lut_prefix": {"zh": "LUT:", "en": "LUT:"},

    # LUT panel
    "luts_title": {"zh": "LUTs", "en": "LUTs"},
    "source_cs": {"zh": "源空间", "en": "Source"},
    "lut_cs": {"zh": "LUT 输入", "en": "LUT input"},
    "watermark": {"zh": "水印", "en": "Watermark"},

    # Dialogs
    "open_image_title": {"zh": "打开图片", "en": "Open Images"},
    "open_image_filter": {
        "zh": "图片 (*.png *.jpg *.jpeg *.ppm *.tif *.bmp *.webp);;所有文件 (*)",
        "en": "Images (*.png *.jpg *.jpeg *.ppm *.tif *.bmp *.webp);;All (*)",
    },
    "open_lut_title": {"zh": "选择 LUT 文件", "en": "Select LUT Files"},
    "open_lut_filter": {
        "zh": "LUT 文件 (*.cube);;所有文件 (*)",
        "en": "LUT Files (*.cube);;All (*)",
    },
    "export_title": {"zh": "导出 LUT 结果", "en": "Export LUT Result"},
    "export_name": {"zh": "klut_结果.png", "en": "klut_result.png"},
    "export_filter": {
        "zh": "PNG (*.png);;JPEG (*.jpg);;所有文件 (*)",
        "en": "PNG (*.png);;JPEG (*.jpg);;All (*)",
    },

    # Status
    "no_luts": {"zh": "未加载 LUT", "en": "No LUTs"},
    "no_image": {"zh": "无图片", "en": "No image"},
    "open_hint": {"zh": "点击「打开」加载图片", "en": "Click Open to start"},

    # Extensions
    "ext_menu": {"zh": "扩展", "en": "Extensions"},
    "ext_manager": {"zh": "管理扩展...", "en": "Manage Extensions..."},
    "no_data_title": {"zh": "无数据", "en": "No Data"},
    "no_data_msg": {
        "zh": "未加载图片或 LUT。\n部分扩展可独立运行。\n\n是否继续？",
        "en": "No images or LUTs loaded.\nSome extensions can work standalone.\n\nContinue anyway?",
    },

    # AI Evaluation Extension
    "ai_eval_title":         {"zh": "AI 风格评估", "en": "AI Style Evaluation"},
    "ai_matched":            {"zh": "匹配", "en": "matched"},
    "ai_no_match":           {"zh": "未找到匹配", "en": "No matches"},
    "ai_eval_sort_by_score": {"zh": "按评分排序", "en": "Sort by score"},

    # Accent colors
    "accent_color": {"zh": "主题色", "en": "Accent Color"},
    "custom_color": {"zh": "自定义...", "en": "Custom..."},

    # Language
    "language": {"zh": "语言", "en": "Language"},
}
