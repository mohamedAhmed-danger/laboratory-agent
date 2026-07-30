import re
import io
import os
import random
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

from models.models import RequestCounter, db

def strip_tags(text: str) -> str:
    """Remove all XML-style tags injected by LLM prompts from a reply string."""
    text = re.sub(r"<SUMMARY>.*?</SUMMARY>",                   "", text, flags=re.DOTALL)
    text = re.sub(r"<INTENT>.*?</INTENT>",                     "", text, flags=re.DOTALL)
    text = re.sub(r"<LAST_BOT_MESSAGE>.*?</LAST_BOT_MESSAGE>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>",                                  "", text)
    return text.strip()


def detect_language_fallback(user_message: str, arabic: str, default: str) -> str:
    """
    Return `arabic` if the user message contains Arabic characters,
    otherwise return `default`.
    Used for error/fallback messages in nodes that must match user language.
    """
    if any("\u0600" <= c <= "\u06ff" for c in user_message):
        return arabic
    return default


PLATFORM_MAP = {
    1: "WhatsApp",
    2: "Facebook",
}

def get_platform_name(platform_id) -> str:
    """Convert platform_id to platform name string."""
    if not platform_id:
        return "unknown"
    try:
        key = int(platform_id)
        return PLATFORM_MAP.get(key, str(platform_id))
    except ValueError:
        return str(platform_id)


def count_request():
    """Decrement the global request counter."""
    try:
        counter = RequestCounter.query.first()
        if counter:
            counter.decrement()
    except Exception as e:
        print(f"[count_request] Error decrementing counter: {e}")


# ── colours ───────────────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#1B4B8A")
CREAM     = colors.HexColor("#F5F0E8")
LIGHT_ROW = colors.HexColor("#EAF0FA")
WHITE     = colors.white
MUTED     = colors.HexColor("#6B7280")
DARK      = colors.HexColor("#1F2937")

# ── font ──────────────────────────────────────────────────────────────────────
_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Cairo.ttf")

def _register_font() -> str:
    try:
        pdfmetrics.registerFont(TTFont("Cairo", _FONT_PATH))
        return "Cairo"
    except Exception:
        return "Helvetica"

# ── Arabic helper ─────────────────────────────────────────────────────────────
def _ar(text: str) -> str:
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text

def _is_arabic(text: str) -> bool:
    return any("\u0600" <= c <= "\u06FF" for c in (text or ""))

# ── style factory ─────────────────────────────────────────────────────────────
def _ps(name_: str, font: str, size: int, color=DARK, align: int = 0) -> ParagraphStyle:
    return ParagraphStyle(
        name_,
        fontName=font,
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=size * 1.45,
    )

def generate_booking_pdf(
    name: str,
    phone: str,
    date: str,
    details: str,
    reference_id: str,
) -> bytes:

    font     = _register_font()
    buffer   = io.BytesIO()
    margin   = 18 * mm
    usable_w = A4[0] - 2 * margin

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=12*mm, bottomMargin=12*mm,
    )

    story = []

    # ── cream header: logo icon + laboratory name ─────────────────────────────
    clinic_ar = _ar("مختبر التحاليل الطبية التخصصي")
    
    hdr = Table(
        [[
            Paragraph("✚", _ps("icon", "Helvetica", 22, NAVY, align=0)),
            Paragraph(clinic_ar, _ps("clin", font, 15, NAVY, align=2)),
        ]],
        colWidths=[16*mm, usable_w - 16*mm],
    )
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CREAM),
        ("TOPPADDING",    (0,0),(-1,-1), 13),
        ("BOTTOMPADDING", (0,0),(-1,-1), 13),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ROUNDEDCORNERS",[8,8,0,0]),
    ]))
    story.append(hdr)

    # ── navy title bar ────────────────────────────────────────────────────────
    title_ar = _ar("تأكيد حجز موعد التحليل")
    
    ttl = Table(
        [[
            Paragraph("Booking Confirmation", _ps("ten", font, 11, WHITE, align=0)),
            Paragraph(title_ar,               _ps("tar", font, 12, WHITE, align=2)),
        ]],
        colWidths=[usable_w/2, usable_w/2],
    )
    ttl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(ttl)

    # ── reference bar ─────────────────────────────────────────────────────────
    ref = Table(
        [[Paragraph(f"Reference: {reference_id}", _ps("ref", font, 10, NAVY, align=1))]],
        colWidths=[usable_w],
    )
    ref.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), CREAM),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("ROUNDEDCORNERS",[0,0,8,8]),
    ]))
    story.append(ref)
    story.append(Spacer(1, 8*mm))

    # ── info rows ─────────────────────────────────────────────────────────────
    fields = [
        ("Patient Name",     "اسم المريض",    name),
        ("Phone",            "رقم الهاتف",    phone),
        ("Appointment Date", "تاريخ الموعد",  date),
        ("Required Analysis","التحاليل المطلوبة", details),
    ]

    rows = []
    for i, (en_lbl, ar_lbl, val) in enumerate(fields):
        lbl_text = f"{en_lbl} / {_ar(ar_lbl)}"
        lbl_cell = Paragraph(lbl_text, _ps(f"l_{i}", font, 9, MUTED, align=0))
        
        val_text  = _ar(val) if _is_arabic(val or "") else (val or "—")
        val_align = 2 if _is_arabic(val or "") else 0
        val_cell  = Paragraph(val_text, _ps(f"v_{i}", font, 11, DARK, align=val_align))
        
        rows.append([lbl_cell, val_cell])

    info = Table(rows, colWidths=[65*mm, usable_w - 65*mm])
    info.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), WHITE),
        ("BACKGROUND",    (0,0),(-1,0),  LIGHT_ROW),
        ("BACKGROUND",    (0,2),(-1,2),  LIGHT_ROW),
        ("LINEBELOW",     (0,0),(-1,-2), 0.5, colors.HexColor("#DDE3EE")),
        ("TOPPADDING",    (0,0),(-1,-1), 12),
        ("BOTTOMPADDING", (0,0),(-1,-1), 12),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ROUNDEDCORNERS",[6,6,6,6]),
    ]))
    story.append(info)
    story.append(Spacer(1, 10*mm))

    # ── footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#C5D0E0")))
    story.append(Spacer(1, 3*mm))
    
    issued    = datetime.now(timezone.utc).strftime("%B %d, %Y  %H:%M UTC")
    footer_ar = _ar("احتفظ بهذه البطاقة للمراجعة")
    
    footer_table = Table(
        [[
            Paragraph(f"Issued: {issued}", _ps("fl", font, 8, MUTED, align=0)),
            Paragraph(footer_ar,           _ps("fr", font, 8, MUTED, align=2)),
        ]],
        colWidths=[usable_w/2, usable_w/2],
    )
    footer_table.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(footer_table)

    doc.build(story)
    return buffer.getvalue()


# ── Ticket PNG Generation ───────────────────────────────────────────────────

PRIMARY       = (99, 102, 241)     # --primary
PRIMARY_DARK  = (79, 70, 229)      # --primary-hover
HERO_TEXT     = (199, 210, 254)    # dashboard hero text tint
PAGE_BG       = (241, 245, 249)    # neutral background
WHITE_COLOR   = (255, 255, 255)
TEXT_PRIMARY  = (15, 23, 42)       # --text-primary
TEXT_MUTED    = (100, 116, 139)    # --text-muted
LINE_COLOR    = (226, 232, 240)    # --surface-border
CONFIRM_GREEN = (16, 185, 129)     # status green

OUTER_W     = 900
CARD_MARGIN = 34
CARD_W      = OUTER_W - 2 * CARD_MARGIN
CARD_LEFT   = CARD_MARGIN
CARD_RIGHT  = OUTER_W - CARD_MARGIN
RADIUS      = 26
PAD         = 40

HEADER_H    = 128
STAMP_R     = 30
STUB_H      = 96
FIELD_GAP_Y = 30
COL_GAP     = 40
_LOGO_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "images", "logo (2).png")


def _ticket_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _is_ar(text: str) -> bool:
    return any("\u0600" <= c <= "\u06FF" for c in (text or ""))


def _prep_text(text: str) -> str:
    return _ar(text) if _is_ar(text or "") else (text or "—")


def _tw_calc(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_right(draw, text, font, right_x, y, fill):
    w = _tw_calc(draw, text, font)
    draw.text((right_x - w, y), text, font=font, fill=fill)
    return w


def _text_left(draw, text, font, left_x, y, fill):
    draw.text((left_x, y), text, font=font, fill=fill)
    return _tw_calc(draw, text, font)


def _wrap_text(draw, text, font, max_w):
    words = (text or "").split(" ")
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if _tw_calc(draw, trial, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _rounded_mask_img(size, radius, corners=(True, True, True, True)):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255, corners=corners
    )
    return mask


def _draw_dashed(draw, x1, x2, y, color, dash=10, gap=8, width=2):
    x = x1
    while x < x2:
        draw.line([x, y, min(x + dash, x2), y], fill=color, width=width)
        x += dash + gap


def _draw_ticket_stamp(draw, cx, cy):
    r = STAMP_R
    draw.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], fill=WHITE_COLOR)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CONFIRM_GREEN)
    draw.line([cx - 13, cy + 1, cx - 4, cy + 12], fill=WHITE_COLOR, width=5)
    draw.line([cx - 4, cy + 12, cx + 15, cy - 10], fill=WHITE_COLOR, width=5)


def _ticket_field_block(draw, label, value_lines, x_right, y, label_font, value_font):
    _text_right(draw, label, label_font, x_right, y, TEXT_MUTED)
    ly = y + label_font.size + 8
    for line in value_lines:
        _text_right(draw, line, value_font, x_right, ly, TEXT_PRIMARY)
        ly += value_font.size + 8
    return ly


def generate_booking_ticket(
    name: str,
    phone: str,
    date: str,
    details: str,
    reference_id: str,
    total_price: float | str | None = None,
) -> bytes:
    """
    Render booking confirmation PNG ticket with patient details, requested services,
    reference ID, and optional calculated total price.
    """
    clinic_name  = _ar("معامل الاختبار للتحاليل الطبية")
    label_font   = _ticket_font(15)
    value_font   = _ticket_font(22)
    details_font = _ticket_font(20)
    name_font    = _ticket_font(25)
    caption_font = _ticket_font(13)
    ref_font     = _ticket_font(15)
    footer_font  = _ticket_font(13)

    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    col_w = (CARD_W - 2 * PAD - COL_GAP) // 2

    name_lines    = _wrap_text(dummy, _prep_text(name), value_font, col_w)
    date_lines    = _wrap_text(dummy, _prep_text(date), value_font, col_w)
    phone_lines   = _wrap_text(dummy, _prep_text(phone), value_font, col_w)
    ref_lines     = [reference_id]
    details_lines = _wrap_text(dummy, _prep_text(details), details_font, CARD_W - 2 * PAD)

    price_str = None
    if total_price is not None:
        price_str = f"{total_price:g} ج.م" if isinstance(total_price, (int, float)) else str(total_price)
    price_lines = _wrap_text(dummy, _prep_text(price_str), value_font, col_w) if price_str else []

    row1_h = max(len(name_lines), len(date_lines)) * (value_font.size + 8) + label_font.size + 8
    row2_h = max(len(phone_lines), len(ref_lines)) * (value_font.size + 8) + label_font.size + 8
    details_h = label_font.size + 8 + len(details_lines) * (details_font.size + 8)
    price_h = (label_font.size + 8 + len(price_lines) * (value_font.size + 8) + FIELD_GAP_Y) if price_lines else 0

    body_h = PAD + row1_h + FIELD_GAP_Y + row2_h + FIELD_GAP_Y + details_h + price_h + PAD
    total_h = int(CARD_MARGIN + HEADER_H + STAMP_R + 6 + body_h + STUB_H + CARD_MARGIN)

    img = Image.new("RGBA", (OUTER_W, total_h), PAGE_BG + (255,))
    card_h = total_h - 2 * CARD_MARGIN

    shadow = Image.new("RGBA", (OUTER_W, total_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [CARD_LEFT, CARD_MARGIN + 10, CARD_RIGHT, CARD_MARGIN + card_h + 10],
        radius=RADIUS, fill=(15, 23, 42, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, shadow)

    card_mask = _rounded_mask_img((CARD_W, card_h), RADIUS)
    card_layer = Image.new("RGBA", (CARD_W, card_h), WHITE_COLOR + (255,))
    img.paste(card_layer, (CARD_LEFT, CARD_MARGIN), card_mask)

    draw = ImageDraw.Draw(img)
    y0 = CARD_MARGIN

    header_layer = Image.new("RGB", (CARD_W, HEADER_H), PRIMARY)
    hd = ImageDraw.Draw(header_layer)
    for x in range(CARD_W):
        t = x / max(CARD_W - 1, 1)
        r = int(PRIMARY[0] + (PRIMARY_DARK[0] - PRIMARY[0]) * t)
        g = int(PRIMARY[1] + (PRIMARY_DARK[1] - PRIMARY[1]) * t)
        b = int(PRIMARY[2] + (PRIMARY_DARK[2] - PRIMARY[2]) * t)
        hd.line([(x, 0), (x, HEADER_H)], fill=(r, g, b))
    header_mask = _rounded_mask_img((CARD_W, HEADER_H), RADIUS, corners=(True, True, False, False))
    img.paste(header_layer, (CARD_LEFT, y0), header_mask)

    logo_size = 62
    halo_r = logo_size // 2 + 8
    logo_cx = CARD_RIGHT - PAD - halo_r
    logo_cy = y0 + HEADER_H // 2
    draw.ellipse([logo_cx - halo_r, logo_cy - halo_r, logo_cx + halo_r, logo_cy + halo_r], fill=WHITE_COLOR)
    try:
        logo = Image.open(_LOGO_PATH).convert("RGBA")
        logo.thumbnail((logo_size, logo_size), Image.LANCZOS)
        img.paste(logo, (logo_cx - logo.width // 2, logo_cy - logo.height // 2), logo)
    except Exception:
        draw.ellipse([logo_cx - logo_size // 2, logo_cy - logo_size // 2, logo_cx + logo_size // 2, logo_cy + logo_size // 2], fill=PRIMARY_DARK)

    name_x_right = logo_cx - halo_r - 18
    _text_right(draw, clinic_name, name_font, name_x_right, y0 + 34, WHITE_COLOR)
    _text_right(draw, "BOOKING CONFIRMATION", caption_font, name_x_right, y0 + 34 + 34, HERO_TEXT)

    _draw_ticket_stamp(draw, CARD_LEFT + PAD + STAMP_R, y0 + HEADER_H)

    right_col_x = CARD_RIGHT - PAD
    left_col_x = right_col_x - col_w - COL_GAP

    row_y = y0 + HEADER_H + STAMP_R + 6 + PAD - STAMP_R
    _ticket_field_block(draw, _ar("اسم المريض"), name_lines, right_col_x, row_y, label_font, value_font)
    _ticket_field_block(draw, _ar("تاريخ الموعد"), date_lines, left_col_x, row_y, label_font, value_font)

    row_y = row_y + row1_h + FIELD_GAP_Y
    _ticket_field_block(draw, _ar("رقم الهاتف"), phone_lines, right_col_x, row_y, label_font, value_font)
    _ticket_field_block(draw, _ar("رقم المرجع"), ref_lines, left_col_x, row_y, label_font, value_font)

    row_y = row_y + row2_h + FIELD_GAP_Y
    draw.line([CARD_LEFT + PAD, row_y - 12, CARD_RIGHT - PAD, row_y - 12], fill=LINE_COLOR, width=1)
    _ticket_field_block(draw, _ar("التحاليل المطلوبة"), details_lines, right_col_x, row_y, label_font, details_font)

    if price_lines:
        row_y = row_y + details_h + FIELD_GAP_Y
        draw.line([CARD_LEFT + PAD, row_y - 12, CARD_RIGHT - PAD, row_y - 12], fill=LINE_COLOR, width=1)
        _ticket_field_block(draw, _ar("إجمالي التكلفة"), price_lines, right_col_x, row_y, label_font, value_font)

    seam_y = y0 + HEADER_H + STAMP_R + 6 + body_h

    notch_r = 15
    draw.ellipse([CARD_LEFT - notch_r, seam_y - notch_r, CARD_LEFT + notch_r, seam_y + notch_r], fill=PAGE_BG)
    draw.ellipse([CARD_RIGHT - notch_r, seam_y - notch_r, CARD_RIGHT + notch_r, seam_y + notch_r], fill=PAGE_BG)
    _draw_dashed(draw, CARD_LEFT + notch_r + 4, CARD_RIGHT - notch_r - 4, seam_y, LINE_COLOR)

    stub_y = seam_y + 22
    rng = random.Random(reference_id)
    bx = CARD_LEFT + PAD
    bar_top, bar_h = stub_y, 34
    while bx < CARD_LEFT + PAD + 220:
        bw = rng.choice([2, 2, 3, 5])
        draw.rectangle([bx, bar_top, bx + bw, bar_top + bar_h], fill=TEXT_PRIMARY)
        bx += bw + rng.choice([3, 5, 7])

    _text_left(draw, reference_id, ref_font, CARD_LEFT + PAD, bar_top + bar_h + 8, TEXT_MUTED)

    issued = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    _text_right(draw, _ar(f"صدرت في {issued}"), footer_font, CARD_RIGHT - PAD, stub_y + 4, TEXT_MUTED)
    _text_right(draw, _ar("احتفظ بهذه الصورة للمراجعة"), footer_font, CARD_RIGHT - PAD, stub_y + 4 + 22, TEXT_MUTED)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()

