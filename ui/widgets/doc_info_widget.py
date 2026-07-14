"""
文档信息展示组件 (QTextBrowser版)

使用富文本HTML格式展示达梦官方文档，提升排版美观度、可读性，并支持字体缩放。
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser
from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QFont


class DocInfoWidget(QWidget):
    """
    文档信息展示组件

    使用QTextBrowser渲染HTML内容，支持:
    - 多级字号缩放
    - 富文本美化显示 (通过CSS)
    - SQL示例点击载入/复制代码
    """

    sql_example_clicked = Signal(str)  # 点击SQL示例时发出信号

    def __init__(self, doc_snippet=None, parent=None):
        super().__init__(parent)
        self._snippet = None
        self._font_zoom_level = 0
        self._init_ui()
        if doc_snippet:
            self.set_snippet(doc_snippet)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)  # 拦截链接点击事件自行处理
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        self.browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: #ffffff;
            }
        """)
        layout.addWidget(self.browser)

    def set_snippet(self, snippet):
        """载入并渲染文档片段"""
        self._snippet = snippet
        if not snippet:
            self.browser.setHtml("<p style='color:#64748b; font-family: sans-serif; font-size:11pt; padding:15px;'>暂无相关文档信息</p>")
            return

        # 构造富文本HTML
        html = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Microsoft YaHei', -apple-system, sans-serif;
                font-size: 10pt;
                line-height: 1.6;
                color: #334155;
                margin: 15px;
            }}
            h2 {{
                color: #0f172a;
                font-size: 14pt;
                margin-top: 0;
                margin-bottom: 8px;
                border-bottom: 2px solid #cbd5e1;
                padding-bottom: 6px;
            }}
            .source {{
                font-size: 9.5pt;
                color: #64748b;
                margin-bottom: 15px;
            }}
            .section-title {{
                font-weight: bold;
                font-size: 11pt;
                color: #1e3a8a;
                margin-top: 15px;
                margin-bottom: 5px;
            }}
            .content-box {{
                background-color: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 6px;
                padding: 12px;
                font-family: Consolas, 'Courier New', monospace;
                white-space: pre-wrap;
                color: #0369a1;
                margin-bottom: 15px;
            }}
            .tips-box {{
                background-color: #fffbeb;
                border: 1px solid #fde68a;
                border-radius: 6px;
                padding: 12px;
                white-space: pre-wrap;
                color: #b45309;
                margin-bottom: 15px;
            }}
            .sql-box {{
                background-color: #1e293b;
                border: 1px solid #0f172a;
                border-radius: 6px;
                padding: 12px;
                margin-top: 5px;
            }}
            .sql-code {{
                font-family: Consolas, monospace;
                color: #38bdf8;
                white-space: pre-wrap;
                margin: 0 0 8px 0;
                font-size: 10pt;
            }}
            .copy-link {{
                color: #38bdf8;
                text-decoration: underline;
                font-size: 9.5pt;
                font-weight: bold;
            }}
            hr {{
                border: 0;
                border-top: 1px solid #334155;
                margin: 10px 0;
            }}
        </style>
        </head>
        <body>
            <h2>📖 {snippet.feature_name}</h2>
            <div class="source">
                <b>文档来源:</b> <a href="{snippet.doc_url}" style="color: #2563eb; text-decoration: none;">{snippet.doc_source}</a>
            </div>
            
            <div class="section-title">📄 文档参考内容:</div>
            <div class="content-box">{snippet.doc_content}</div>
            
            <div class="section-title">💡 优化排查提示:</div>
            <div class="tips-box">{snippet.tips}</div>
        """

        if snippet.sql_examples:
            html += '<div class="section-title">📝 推荐SQL示例 (点击加载至编辑器):</div>'
            html += '<div class="sql-box">'
            for i, sql in enumerate(snippet.sql_examples):
                if sql.strip().startswith("--"):
                    html += f'<div style="color: #94a3b8; font-style: italic; font-size: 9.5pt; margin-top: 5px; margin-bottom: 5px;">{sql}</div>'
                else:
                    html += f'<pre class="sql-code">{sql}</pre>'
                    html += f'<div style="text-align: right;"><a href="copy-sql://{i}" class="copy-link">▶ 复制并载入此SQL</a></div>'
                    if i < len(snippet.sql_examples) - 1:
                        html += '<hr>'
            html += '</div>'

        html += """
        </body>
        </html>
        """
        self.browser.setHtml(html)

        # 重新应用当前的缩放比例
        if self._font_zoom_level > 0:
            self.browser.zoomIn(self._font_zoom_level)
        elif self._font_zoom_level < 0:
            self.browser.zoomOut(abs(self._font_zoom_level))

    def get_snippet(self):
        return self._snippet

    def zoom_in(self):
        """放大字体"""
        self.browser.zoomIn(1)
        self._font_zoom_level += 1

    def zoom_out(self):
        """缩小字体"""
        self.browser.zoomOut(1)
        self._font_zoom_level -= 1

    def reset_zoom(self):
        """恢复默认字体大小"""
        if self._font_zoom_level > 0:
            self.browser.zoomOut(self._font_zoom_level)
        elif self._font_zoom_level < 0:
            self.browser.zoomIn(abs(self._font_zoom_level))
        self._font_zoom_level = 0

    def _on_anchor_clicked(self, url: QUrl):
        url_str = url.toString()
        if url_str.startswith("copy-sql://"):
            try:
                idx = int(url_str.split("://")[1])
                if self._snippet and 0 <= idx < len(self._snippet.sql_examples):
                    sql = self._snippet.sql_examples[idx]
                    self.sql_example_clicked.emit(sql)
            except Exception:
                pass
        else:
            # 打开外部浏览器
            import webbrowser
            webbrowser.open(url_str)
