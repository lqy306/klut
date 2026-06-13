"""
ext_ai.py — AI 风格评估扩展
=============================
可选扩展模块。运行时由主程序动态加载。

接口: 直接 `import ext_ai` 即可注册菜单项。
     调用 `ext_ai.launch(parent, images, luts, lut_paths, src_cs, lut_cs)` 启动。
"""

import os, sys, json
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QProgressBar,
    QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox,
    QApplication, QGroupBox, QFormLayout)

from ai_eval import *
from engine.lut3d import load_lut
from colorspaces import convert_image, ids as _cs_ids
from lang import tr, LANG

_EXT_DIR = os.path.dirname(__file__)
_CONFIG_PATH = os.path.join(_EXT_DIR, "config.json")


def _load_config():
    """加载拓展自己的持久化配置"""
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(cfg):
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _ext_api_config():
    """返回 (key, url, model) — 拓展设置优先, 回退环境变量"""
    cfg = _load_config()
    key = cfg.get("api_key", "") or os.environ.get("OPENAI_API_KEY", "")
    url = cfg.get("base_url", "") or os.environ.get("OPENAI_BASE_URL", DEFAULT_API_URL)
    mdl = cfg.get("model", "") or os.environ.get("OPENAI_MODEL", "deepseek-v4-flash")
    return key, url, mdl


def menu_id():
    return "ext_ai"


# ============================================================
#  拓展语言包
# ============================================================

_STRINGS = {
    "api_settings":    {"zh": "API 设置（点击收起）", "en": "API Settings (click collapse)"},
    "api_key":         {"zh": "API Key", "en": "API Key"},
    "base_url":        {"zh": "Base URL", "en": "Base URL"},
    "model":           {"zh": "模型", "en": "Model"},
    "start":           {"zh": "开始评估", "en": "Start Evaluation"},
    "status_ready":    {"zh": "就绪 — 点击开始评估", "en": "Ready — press Start Evaluation"},
    "status_collect":  {"zh": "正在收集色彩统计...", "en": "Collecting color stats..."},
    "status_calling":  {"zh": "正在调用 AI...", "en": "Calling AI..."},
    "status_failed":   {"zh": "统计失败, 请检查数据", "en": "Stats collection failed"},
    "status_fallback": {"zh": "AI 未返回, 使用本地分析", "en": "AI no response, local fallback"},
    "status_best":     {"zh": "🏆 最佳", "en": "🏆 Best"},
    "export_json":     {"zh": "导出 JSON", "en": "Export JSON"},
    "export_report":   {"zh": "📄 报告", "en": "📄 Report"},
    "close":           {"zh": "关闭", "en": "Close"},
    "query_label":     {"zh": "风格查询:", "en": "Query:"},
    "query_hint":      {"zh": "输入风格描述: 德味 / 电影感 / 复古", "en": "e.g. vintage / cinematic / warm"},
    "query_btn":       {"zh": "查询", "en": "Query"},
    "no_key":          {"zh": "未设置 API Key。请在 API Settings 中输入。", "en": "API Key not set. Add it in API Settings."},
    "querying":        {"zh": "🔍 查询中...", "en": "🔍 Querying..."},
    "no_match":        {"zh": "未找到匹配", "en": "No matches"},
    "matched":         {"zh": "匹配", "en": "matched"},
    "results":         {"zh": "个结果", "en": "results"},
    "report_title":    {"zh": "导出报告", "en": "Export Report"},
    "json_title":      {"zh": "导出 JSON", "en": "Export JSON"},
    "exported_ok":     {"zh": "✓ 已导出", "en": "✓ Exported"},
    "rank":            {"zh": "排名", "en": "Rank"},
    "score":           {"zh": "评分", "en": "Score"},
    "best_lut":        {"zh": "最佳 LUT", "en": "Best LUT"},
    "reason":          {"zh": "理由", "en": "Reason"},
}


def _S(key):
    from lang import ext_tr
    return ext_tr(_STRINGS, key)


def menu_label():
    return {"zh": "AI 风格评估", "en": "AI Evaluation"}.get(LANG.get(), "AI Evaluation")


def _cs_id(idx):
    """Map old CS integer index to new string ID."""
    all_ids = _cs_ids()
    return all_ids[idx] if 0 <= idx < len(all_ids) else "rec709"


def launch(parent, images, luts, lut_paths, src_cs=0, lut_cs=0):
    import logging
    _log = logging.getLogger("klut")
    try:
        dlg = AiEvalDialog(parent, images, luts, lut_paths, src_cs, lut_cs)
    except Exception as e:
        _log.error("AiEvalDialog init failed: %s", e)
        import traceback; traceback.print_exc()
        return

    # Center on primary screen (avoids off-screen with parent=None)
    try:
        dlg.resize(700, 500)
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            dlg.move(geo.x() + (geo.width() - dlg.width()) // 2,
                     geo.y() + (geo.height() - dlg.height()) // 2)
    except Exception:
        pass  # non-critical

    dlg.setWindowModality(Qt.ApplicationModal)
    _log.info("AiEvalDialog showing…")
    dlg.exec_()
    _log.info("AiEvalDialog closed")


# ============================================================
#  对话框
# ============================================================

class AiEvalDialog(QDialog):
    def __init__(self, parent, images, luts, lut_paths,
                 src_cs=0, lut_cs=0):
        super().__init__(parent)
        lang = LANG.get()
        if lang == "en":
            set_lang("en")
        else:
            set_lang("zh")
        self.setWindowTitle(tr("ai_eval_title"))
        self.setMinimumSize(700, 500)
        self.images = images
        self.luts = luts
        self.lut_paths = lut_paths
        self.src_cs = src_cs
        self.lut_cs = lut_cs
        self._src_id = _cs_id(src_cs)
        self._lut_id = _cs_id(lut_cs)
        self._last_results = []
        self._last_best = ""
        self._last_reason = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # API 配置 (可展开/收起)
        self._cfg = _load_config()
        cfg_group = QGroupBox(_S("api_settings"))
        cfg_group.setCheckable(True)
        cfg_group.setChecked(True)
        cfg_group.setStyleSheet(
            "QGroupBox { color: #888; font-size: 11px; border: 1px solid #333; "
            "border-radius: 4px; margin-top: 8px; padding: 12px 8px 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        cf = QFormLayout(cfg_group)
        self._cfg_key = QLineEdit(self._cfg.get("api_key", ""))
        self._cfg_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cfg_key.setPlaceholderText("sk-...")
        cf.addRow(_S("api_key"), self._cfg_key)
        self._cfg_url = QLineEdit(self._cfg.get("base_url", "https://api.openai.com/v1"))
        cf.addRow(_S("base_url"), self._cfg_url)
        self._cfg_model = QLineEdit(self._cfg.get("model", "deepseek-v4-flash"))
        cf.addRow(_S("model"), self._cfg_model)
        layout.addWidget(cfg_group)

        self.status_label = QLabel(_S("status_ready"))
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "LUT", "Score", "Tags"])
        self.tree.setColumnWidth(0, 40)
        self.tree.setColumnWidth(1, 180)
        self.tree.setColumnWidth(2, 55)
        layout.addWidget(self.tree, 1)

        self.output = QTextEdit()
        self.output.setMaximumHeight(120)
        self.output.setVisible(False)
        layout.addWidget(self.output)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.btn_eval = QPushButton(_S("start"))
        self.btn_eval.clicked.connect(self._run_eval)
        self.btn_eval.setObjectName("primary")
        btn_layout.addWidget(self.btn_eval)

        self.btn_export = QPushButton(_S("export_json"))
        self.btn_export.clicked.connect(self._export_json)
        self.btn_export.setEnabled(False)
        btn_layout.addWidget(self.btn_export)

        self.btn_report = QPushButton(_S("export_report"))
        self.btn_report.clicked.connect(self._export_report)
        self.btn_report.setEnabled(False)
        btn_layout.addWidget(self.btn_report)

        self.btn_close = QPushButton(_S("close"))
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        query_layout = QHBoxLayout()
        query_layout.addWidget(QLabel(_S("query_label")))
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(_S("query_hint"))
        self.query_input.returnPressed.connect(self._run_query)
        query_layout.addWidget(self.query_input, 1)
        btn_query = QPushButton(_S("query_btn"))
        btn_query.clicked.connect(self._run_query)
        query_layout.addWidget(btn_query)
        layout.addLayout(query_layout)

    def _save_cfg(self):
        """保存 API 配置到文件"""
        cfg = {
            "api_key": self._cfg_key.text().strip(),
            "base_url": self._cfg_url.text().strip(),
            "model": self._cfg_model.text().strip(),
        }
        _save_config(cfg)

    def _run_eval(self):
        self._save_cfg()
        api_key, base_url, model = _ext_api_config()
        if not api_key:
            QMessageBox.warning(self, "klut", _S("no_key"))
            return

        self.btn_eval.setEnabled(False)
        self.status_label.setText(_S("status_collect"))
        self.progress.setValue(0)
        self.tree.clear()

        stats_list = []
        from PIL import Image as PILImage
        total = max(1, len(self.luts) * len(self.images))
        done = 0

        for img_path in self.images:
            for i, lut_name in enumerate(self.luts):
                if i >= len(self.lut_paths):
                    continue
                done += 1
                self.progress.setValue(done * 50 // total)

                pil_img = PILImage.open(img_path).convert("RGB")
                # Small thumbnail is enough for color-stat extraction
                pil_img.thumbnail((256, 256), PILImage.LANCZOS)
                if self.src_cs != self.lut_cs:
                    pil_img = convert_image(pil_img, self._src_id, self._lut_id)
                lut = load_lut(lut_name, os.path.dirname(self.lut_paths[i]))
                if lut:
                    pil_img = lut.apply_image(pil_img)
                if self.src_cs != self.lut_cs:
                    pil_img = convert_image(pil_img, self._lut_id, self._src_id)

                key = f"{lut_name}" if len(self.images) <= 1 else \
                      f"{lut_name} ({os.path.basename(img_path)})"
                s = extract_stats(pil_img, key)
                if s:
                    stats_list.append((key, s))
                QApplication.processEvents()

        self.progress.setValue(50)
        if not stats_list:
            self.status_label.setText(_S("status_failed"))
            self.btn_eval.setEnabled(True)
            return

        self.status_label.setText(_S("status_calling"))
        self.output.setVisible(True)
        self.output.clear()
        QApplication.processEvents()

        def on_chunk(c):
            self.output.insertPlainText(c)
            self.output.ensureCursorVisible()
            QApplication.processEvents()

        results, best, reason = evaluate(
            stats_list, api_key, model, base_url, stream_cb=on_chunk)
        if not results:
            self.status_label.setText(_S("status_fallback"))
            results = local_evaluate(stats_list)

        self.progress.setValue(100)
        self.tree.clear()
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for r in results:
            item = QTreeWidgetItem([
                medals.get(r.rank, str(r.rank)), r.name,
                f"{r.score:.0f}", ",".join(r.style_tags[:3])])
            item.setToolTip(2, r.description)
            item.setToolTip(3, r.analysis[:200])
            if r.rank <= 3:
                for c in range(4):
                    item.setForeground(c, QColor("#f90"))
            self.tree.addTopLevelItem(item)

        self._last_results = results
        self._last_best = best
        self._last_reason = reason
        self.btn_eval.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_report.setEnabled(True)
        self.status_label.setText(f"{_S('status_best')}: {best}")

    def _run_query(self):
        q = self.query_input.text().strip()
        if not q or not self._last_results:
            return
        api_key, base_url, model = _ext_api_config()
        if not api_key:
            return
        self.output.setVisible(True)
        self.output.clear()
        self.status_label.setText(f"{_S('querying')} {q} ...")
        QApplication.processEvents()

        def on_chunk(c):
            self.output.insertPlainText(c)
            self.output.ensureCursorVisible()
            QApplication.processEvents()

        matches = query_match(
            self._last_results, q, api_key, model, base_url, stream_cb=on_chunk)

        if matches:
            self.tree.clear()
            for i, m in enumerate(matches[:5]):
                item = QTreeWidgetItem([
                    {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, str(i+1)),
                    m.get("name", "?"), f"{m.get('relevance', 0)}%",
                    m.get("reason", "")[:60]])
                self.tree.addTopLevelItem(item)
            self.status_label.setText(
                f"🔍 \"{q}\" {tr('ai_matched')} {len(matches)} results")
        else:
            self.status_label.setText(f"🔍 {tr('ai_no_match')}")

    def _export_json(self):
        if not self._last_results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, _S("export_title"), "eval_result.json", "JSON (*.json)")
        if not path:
            return
        data = {
            "best_lut": self._last_best,
            "best_reason": self._last_reason,
            "rankings": [asdict(r) for r in self._last_results],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.status_label.setText(f"✓ exported: {path}")

    def _export_report(self):
        if not self._last_results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "eval_report.md",
            "Markdown (*.md);;PDF (*.pdf)")
        if not path:
            return
        is_pdf = path.endswith(".pdf")
        md_path = path.replace(".pdf", ".md") if is_pdf else path

        # 生成 Markdown
        medals = {1:"🥇", 2:"🥈", 3:"🥉"}
        lines = []
        lines.append(f"# LUT Evaluation Report\n")
        lines.append(f"**Best LUT**: `{self._last_best}`  \n")
        if self._last_reason:
            lines.append(f"**Reason**: {self._last_reason}  \n")
        lines.append(f"\n## Rankings\n")
        lines.append("| Rank | LUT | Score | Style Tags |")
        lines.append("|------|-----|-------|------------|")
        for r in self._last_results:
            rank = medals.get(r.rank, str(r.rank))
            tags = ", ".join(r.style_tags)
            desc = r.description.replace("|", "\\|")
            lines.append(f"| {rank} | `{r.name}` | {r.score:.0f} | {tags} |")
        lines.append("")
        lines.append("## Details\n")
        for r in self._last_results:
            rank = medals.get(r.rank, str(r.rank))
            lines.append(f"### {rank} {r.name}  — {r.score:.0f}/100\n")
            lines.append(f"- **Tags**: {', '.join(r.style_tags)}")
            lines.append(f"- **Description**: {r.description}")
            lines.append(f"- **Analysis**: {r.analysis}")
            lines.append("")

        md = "\n".join(lines)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)
        self.status_label.setText(f"✓ Markdown: {md_path}")

        if is_pdf:
            self._md_to_pdf(md_path, path)

    def _md_to_pdf(self, md_path, pdf_path):
        """尝试将 MD 转为 PDF (多种引擎)"""
        # 1) pandoc
        import shutil, subprocess
        if shutil.which("pandoc"):
            try:
                subprocess.run(["pandoc", md_path, "-o", pdf_path,
                                "--pdf-engine=xelatex"], timeout=60,
                               capture_output=True)
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    self.status_label.setText(f"✓ PDF: {pdf_path}")
                    return
            except Exception:
                pass

        # 2) wkhtmltopdf
        if shutil.which("wkhtmltopdf"):
            try:
                # Markdown → HTML 直接嵌入
                with open(md_path, 'r', encoding='utf-8') as f:
                    md_text = f.read()
                html = f"""<!DOCTYPE html><html><meta charset="utf-8">
<body><pre style="font:14px/1.6 sans-serif;max-width:800px;margin:auto">
{md_text}</pre></body></html>"""
                html_path = md_path.replace(".md", ".html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                subprocess.run(["wkhtmltopdf", html_path, pdf_path],
                               timeout=60, capture_output=True)
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    self.status_label.setText(f"✓ PDF: {pdf_path}")
                    return
            except Exception:
                pass

        # 3) 纯 Qt 简易 PDF (无外部工具时)
        try:
            from PySide6.QtGui import QPdfWriter, QPainter, QFont, QColor
            from PySide6.QtCore import QSizeF, QMarginsF
            pw = QPdfWriter(pdf_path)
            pw.setPageSizeMM(QSizeF(210, 297))  # A4
            pw.setPageMargins(QMarginsF(15, 15, 15, 15))
            painter = QPainter(pw)
            painter.setFont(QFont("sans", 10))

            with open(md_path, 'r', encoding='utf-8') as f:
                text = f.read()

            y = 30
            for line in text.split("\n"):
                if painter is None:
                    break
                if y > 270:
                    pw.newPage()
                    y = 30
                painter.drawText(10, y, 170, 20, 0, line[:120])
                y += 6
            painter.end()
            self.status_label.setText(f"✓ PDF: {pdf_path}")
            return
        except Exception as e:
            self.status_label.setText(f"PDF failed (install pandoc): {e}")
