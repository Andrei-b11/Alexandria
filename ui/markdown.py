"""Conversor Markdown → HTML ligero para el chat y las notas.

Cubre lo que generan los modelos: títulos, listas, negrita/cursiva, código en
línea y bloques de código. Sin dependencias externas.
"""
import html
import re


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r'<code style="background:#23252b; padding:1px 5px; border-radius:4px;">\1</code>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"<i>\1</i>", text)
    return text


def md_to_html(text: str) -> str:
    lines = (text or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    in_code = False
    code_buf: list[str] = []
    list_mode: str | None = None  # "ul" | "ol" | None

    def close_list():
        nonlocal list_mode
        if list_mode:
            out.append(f"</{list_mode}>")
            list_mode = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                out.append(
                    '<pre style="background:#191b20; border:1px solid #2a2d33; '
                    'border-radius:8px; padding:10px; font-size:12px;">'
                    + html.escape("\n".join(code_buf)) + "</pre>"
                )
                code_buf = []
                in_code = False
            else:
                close_list()
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            close_list()
            level = len(m.group(1))
            size = {1: 19, 2: 17, 3: 15, 4: 14}[level]
            out.append(
                f'<p style="font-size:{size}px; font-weight:600; color:#f2f3f5; '
                f'margin:14px 0 4px 0;">{_inline(m.group(2))}</p>'
            )
            continue

        m = re.match(r"^[-*•]\s+(.*)$", stripped)
        if m:
            if list_mode != "ul":
                close_list()
                out.append('<ul style="margin:4px 0 4px 18px; -qt-list-indent:1;">')
                list_mode = "ul"
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        m = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if m:
            if list_mode != "ol":
                close_list()
                out.append('<ol style="margin:4px 0 4px 18px; -qt-list-indent:1;">')
                list_mode = "ol"
            out.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        close_list()
        if not stripped:
            continue
        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            out.append('<hr style="border:none; border-top:1px solid #2a2d33;">')
            continue
        out.append(f'<p style="margin:5px 0; line-height:1.45;">{_inline(stripped)}</p>')

    if in_code and code_buf:
        out.append("<pre>" + html.escape("\n".join(code_buf)) + "</pre>")
    close_list()
    return "".join(out)
