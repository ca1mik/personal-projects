from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap


OUT_DIR = Path(r"F:\projeck_svyaz")
W, H = 4200, 2970  # A3 landscape, 10 px/mm


def mm(value: float) -> int:
    return int(round(value * 10))


def load_font(size: int, bold: bool = False):
    paths = []
    if bold:
        paths.extend(
            [
                r"C:\Windows\Fonts\arialbd.ttf",
                r"C:\Windows\Fonts\calibrib.ttf",
                r"C:\Windows\Fonts\verdanab.ttf",
            ]
        )
    else:
        paths.extend(
            [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\calibri.ttf",
                r"C:\Windows\Fonts\verdana.ttf",
            ]
        )
    for candidate in paths:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONT_XS = load_font(22)
FONT_S = load_font(26)
FONT_M = load_font(32)
FONT_B = load_font(38, bold=True)
FONT_H = load_font(48, bold=True)


def rect(draw, box, width=2, fill=None):
    draw.rectangle(box, outline="black", width=width, fill=fill)


def line(draw, xy, width=2):
    draw.line(xy, fill="black", width=width)


def center_text(draw, center, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = center[0] - (bbox[2] - bbox[0]) // 2
    y = center[1] - (bbox[3] - bbox[1]) // 2
    draw.text((x, y), text, fill="black", font=font)


def text_box(draw, box, text, font, align="left", padding=8, spacing=4):
    x1, y1, x2, y2 = box
    avg_char_width = max(11, font.size // 2)
    wrap_width = max(8, (x2 - x1 - 2 * padding) // avg_char_width)
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=wrap_width) or [""])
    y = y1 + padding
    for entry in lines:
        bbox = draw.textbbox((0, 0), entry, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if y + th > y2 - padding:
            break
        if align == "center":
            x = x1 + ((x2 - x1) - tw) // 2
        else:
            x = x1 + padding
        draw.text((x, y), entry, fill="black", font=font)
        y += th + spacing


def arrow(draw, start, end, width=3):
    line(draw, (*start, *end), width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 > x1 else -1
        pts = [(x2, y2), (x2 - sign * 26, y2 - 14), (x2 - sign * 26, y2 + 14)]
    else:
        sign = 1 if y2 > y1 else -1
        pts = [(x2, y2), (x2 - 14, y2 - sign * 26), (x2 + 14, y2 - sign * 26)]
    draw.polygon(pts, fill="black")


def connection(draw, start, end, width=2):
    line(draw, (*start, *end), width=width)


def net_label(draw, x, y, text):
    bbox = draw.textbbox((0, 0), text, font=FONT_XS)
    w = bbox[2] - bbox[0] + 18
    h = bbox[3] - bbox[1] + 10
    rect(draw, (x, y, x + w, y + h), width=1, fill="white")
    draw.text((x + 9, y + 4), text, fill="black", font=FONT_XS)


def block(draw, box, title, body=None):
    x1, y1, x2, y2 = box
    rect(draw, box, width=2)
    line(draw, (x1, y1 + 48, x2, y1 + 48), width=2)
    center_text(draw, ((x1 + x2) // 2, y1 + 24), title, FONT_S)
    if body:
        text_box(draw, (x1 + 4, y1 + 50, x2 - 4, y2 - 4), body, FONT_XS)


def draw_frame(draw):
    left = mm(20)
    top = mm(5)
    right = W - mm(5)
    bottom = H - mm(5)
    rect(draw, (left, top, right, bottom), width=3)
    return left, top, right, bottom


def draw_title_block(draw, frame, document_name, designation, stage, sheet_no, total_sheets):
    left, top, right, bottom = frame
    tb_h = mm(55)
    tb_w = mm(185)
    rev_w = mm(70)
    y1 = bottom - tb_h
    x1 = right - tb_w
    rev_x1 = x1 - rev_w

    # full lower band line
    line(draw, (left, y1, right, y1), width=2)
    # revision table
    rect(draw, (rev_x1, y1, x1, bottom), width=2)
    for x in [rev_x1 + mm(10), rev_x1 + mm(23), rev_x1 + mm(45), rev_x1 + mm(57)]:
        line(draw, (x, y1, x, bottom), width=1)
    for y in [y1 + mm(11), y1 + mm(22), y1 + mm(33), y1 + mm(44)]:
        line(draw, (rev_x1, y, x1, y), width=1)

    # title block
    rect(draw, (x1, y1, right, bottom), width=2)
    for y in [y1 + mm(12), y1 + mm(24), y1 + mm(36), y1 + mm(46)]:
        line(draw, (x1, y, right, y), width=1)
    for x in [x1 + mm(120), x1 + mm(138), x1 + mm(154), x1 + mm(170)]:
        line(draw, (x, y1 + mm(36), x, bottom), width=1)
    line(draw, (x1 + mm(120), y1, x1 + mm(120), y1 + mm(24)), width=1)
    line(draw, (x1 + mm(145), y1, x1 + mm(145), y1 + mm(24)), width=1)
    line(draw, (x1 + mm(120), y1 + mm(12), right, y1 + mm(12)), width=1)

    text_box(draw, (x1 + 8, y1 + 6, x1 + mm(118), y1 + mm(24) - 4), document_name, FONT_S)
    center_text(draw, (x1 + mm(132), y1 + mm(6)), stage, FONT_XS)
    center_text(draw, (x1 + mm(158), y1 + mm(6)), "Лит.", FONT_XS)
    text_box(draw, (x1 + mm(122), y1 + mm(14), right - 6, y1 + mm(24) - 4), designation, FONT_XS)

    text_box(draw, (x1 + 8, y1 + mm(24) + 2, x1 + mm(118), y1 + mm(36) - 2), "Разраб. Codex", FONT_XS)
    text_box(draw, (x1 + 8, y1 + mm(36) + 2, x1 + mm(118), y1 + mm(46) - 2), "Пров. -", FONT_XS)
    text_box(draw, (x1 + 8, y1 + mm(46) + 2, x1 + mm(118), bottom - 2), "Н.контр. -", FONT_XS)

    center_text(draw, (x1 + mm(129), y1 + mm(40)), "Лист", FONT_XS)
    center_text(draw, (x1 + mm(146), y1 + mm(40)), "Листов", FONT_XS)
    center_text(draw, (x1 + mm(162), y1 + mm(40)), "Масш.", FONT_XS)
    center_text(draw, (x1 + mm(177), y1 + mm(40)), "Формат", FONT_XS)
    center_text(draw, (x1 + mm(129), y1 + mm(50)), str(sheet_no), FONT_S)
    center_text(draw, (x1 + mm(146), y1 + mm(50)), str(total_sheets), FONT_S)
    center_text(draw, (x1 + mm(162), y1 + mm(50)), "1:1", FONT_XS)
    center_text(draw, (x1 + mm(177), y1 + mm(50)), "A3", FONT_S)

    text_box(
        draw,
        (left + 8, y1 + 6, rev_x1 - 8, y1 + mm(22)),
        "Оптоволоконная система связи. Дальность 7-10 км. Концептуальный комплект схем.",
        FONT_XS,
    )
    return y1


def sheet(document_name, designation, stage, sheet_no, total_sheets):
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    frame = draw_frame(draw)
    content_bottom = draw_title_block(draw, frame, document_name, designation, stage, sheet_no, total_sheets)
    content = (mm(28), mm(22), W - mm(16), content_bottom - mm(10))
    return img, draw, frame, content


def structural_sheet():
    img, draw, frame, content = sheet("Схема электрическая структурная", "ПС.Э1", "Э1", 1, 5)
    x1, y1, x2, y2 = content
    center_text(draw, ((x1 + x2) // 2, y1 + 20), "СТРУКТУРНАЯ СХЕМА СИСТЕМЫ", FONT_H)

    block(draw, (mm(38), mm(60), mm(125), mm(150)), "БЛОК А", "Интерфейс абонента\nАудиотракт\nКонтроллер\nОптический модуль\nПитание")
    block(draw, (mm(167), mm(78), mm(253), mm(132)), "ОПТИЧЕСКАЯ ЛИНИЯ", "Одномодовое волокно\n1310 нм\nTX / RX\n7-10 км")
    block(draw, (mm(295), mm(60), mm(382), mm(150)), "БЛОК Б", "Интерфейс абонента\nАудиотракт\nКонтроллер\nОптический модуль\nПитание")

    arrow(draw, (mm(125), mm(95)), (mm(167), mm(95)), width=4)
    arrow(draw, (mm(253), mm(113)), (mm(295), mm(113)), width=4)
    arrow(draw, (mm(295), mm(125)), (mm(253), mm(125)), width=4)
    arrow(draw, (mm(167), mm(145)), (mm(125), mm(145)), width=4)

    block(draw, (mm(55), mm(180), mm(108), mm(232)), "ПИТАНИЕ А", "VIN 9..18 В\nили АКБ")
    block(draw, (mm(312), mm(180), mm(365), mm(232)), "ПИТАНИЕ Б", "VIN 9..18 В\nили АКБ")
    arrow(draw, (mm(81), mm(180)), (mm(81), mm(150)), width=3)
    arrow(draw, (mm(338), mm(180)), (mm(338), mm(150)), width=3)

    text_box(
        draw,
        (mm(35), mm(244), mm(385), mm(262)),
        "Функциональные части изделия показаны прямоугольниками. Связи между частями показаны линиями со стрелками.",
        FONT_XS,
    )
    return img


def functional_sheet():
    img, draw, frame, content = sheet("Схема электрическая функциональная", "ПС.Э2", "Э2", 2, 5)
    x1, y1, x2, y2 = content
    center_text(draw, ((x1 + x2) // 2, y1 + 20), "ФУНКЦИОНАЛЬНАЯ СХЕМА ОКОНЕЧНОГО БЛОКА", FONT_H)

    top_y1 = mm(62)
    top_y2 = mm(125)
    blocks = [
        (mm(30), mm(70), "J20 МИКРОФОН", "Речевой вход"),
        (mm(98), mm(70), "U20 ПРЕДУСИЛИТЕЛЬ", "Усиление\nФильтрация"),
        (mm(166), mm(70), "U21 КОДЕК", "АЦП/ЦАП\nОцифровка"),
        (mm(234), mm(70), "U10 КОНТРОЛЛЕР", "Логика\nВызов\nДиагностика"),
        (mm(302), mm(70), "U40/U41\nОПТ. ТРАНСПОРТ", "TX/RX\nКонтроль линка"),
    ]
    for x, y, title, body in blocks:
        block(draw, (x, top_y1, x + mm(55), top_y2), title, body)

    for start_x in [mm(85), mm(153), mm(221), mm(289)]:
        arrow(draw, (start_x, mm(101)), (start_x + mm(13), mm(101)), width=3)
    block(draw, (mm(370), mm(70), mm(405), mm(125)), "J40/J41", "Оптика\nВолокно")
    arrow(draw, (mm(357), mm(101)), (mm(370), mm(101)), width=3)

    block(draw, (mm(32), mm(155), mm(112), mm(220)), "S1/S2 ОРГАНЫ\nУПРАВЛЕНИЯ", "Вызов\nПередача PTT")
    block(draw, (mm(126), mm(155), mm(195), mm(220)), "LED/BZ\nИНДИКАЦИЯ", "Питание\nВызов\nTX\nАвария")
    block(draw, (mm(210), mm(155), mm(280), mm(220)), "U1..U4 ПИТАНИЕ", "VIN\n+5V\n+3V3_DIG\n+3V3_ANA\n+VAMP")
    block(draw, (mm(295), mm(155), mm(377), mm(220)), "U30 УСИЛИТЕЛЬ НЧ /\nJ30 ГРОМКОГОВОРИТЕЛЬ", "Выход на\nгромкоговоритель")

    arrow(draw, (mm(112), mm(187)), (mm(234), mm(187)), width=3)
    arrow(draw, (mm(195), mm(187)), (mm(234), mm(187)), width=3)
    arrow(draw, (mm(245), mm(155)), (mm(245), mm(125)), width=3)
    arrow(draw, (mm(280), mm(187)), (mm(302), mm(187)), width=3)
    arrow(draw, (mm(336), mm(155)), (mm(336), mm(125)), width=3)
    arrow(draw, (mm(336), mm(125)), (mm(388), mm(125)), width=3)

    net_label(draw, mm(175), mm(85), "AUDIO_DATA")
    net_label(draw, mm(260), mm(85), "CTRL / STATUS")
    net_label(draw, mm(240), mm(145), "PWR_GOOD / VBAT_ADC")
    return img


def principal_power_control():
    img, draw, frame, content = sheet("Схема электрическая принципиальная", "ПС.Э3.1", "Э3", 3, 5)
    x1, y1, x2, y2 = content
    center_text(draw, ((x1 + x2) // 2, y1 + 20), "ПРИНЦИПИАЛЬНАЯ СХЕМА. ПИТАНИЕ И ЛОГИКА", FONT_H)

    # Power chain
    power_y = mm(78)
    line(draw, (mm(35), power_y, mm(210), power_y), width=3)
    center_text(draw, (mm(35), power_y - 22), "J1", FONT_S)
    center_text(draw, (mm(35), power_y + 18), "VIN", FONT_XS)
    rect(draw, (mm(48), mm(72), mm(60), mm(84)), width=2)
    center_text(draw, (mm(54), mm(63)), "F1", FONT_XS)
    rect(draw, (mm(72), mm(68), mm(90), mm(88)), width=2)
    center_text(draw, (mm(81), mm(60)), "D1", FONT_XS)
    rect(draw, (mm(102), mm(68), mm(124), mm(88)), width=2)
    center_text(draw, (mm(113), mm(60)), "Q1", FONT_XS)
    block(draw, (mm(140), mm(58), mm(205), mm(98)), "U1", "DC/DC\n+5V_MAIN")
    block(draw, (mm(35), mm(110), mm(85), mm(150)), "U2", "LDO\n+3V3_DIG")
    block(draw, (mm(95), mm(110), mm(145), mm(150)), "U3", "LDO\n+3V3_ANA")
    block(draw, (mm(155), mm(110), mm(205), mm(150)), "U4", "REG\n+VAMP")
    connection(draw, (mm(172), mm(98)), (mm(60), mm(110)), width=2)
    connection(draw, (mm(172), mm(98)), (mm(120), mm(110)), width=2)
    connection(draw, (mm(182), mm(98)), (mm(180), mm(110)), width=2)

    block(draw, (mm(240), mm(52), mm(322), mm(110)), "U10", "Контроллер\nGPIO / ADC\nUART/SPI/I2S")
    block(draw, (mm(336), mm(52), mm(372), mm(78)), "Y1", "Кварц")
    block(draw, (mm(336), mm(84), mm(372), mm(110)), "U11", "RESET")
    connection(draw, (mm(322), mm(66)), (mm(336), mm(66)), width=2)
    connection(draw, (mm(322), mm(97)), (mm(336), mm(97)), width=2)

    block(draw, (mm(240), mm(132), mm(285), mm(175)), "S1", "CALL")
    block(draw, (mm(292), mm(132), mm(337), mm(175)), "S2", "PTT")
    connection(draw, (mm(262), mm(132)), (mm(262), mm(110)), width=2)
    connection(draw, (mm(314), mm(132)), (mm(314), mm(110)), width=2)
    net_label(draw, mm(244), mm(114), "KEY_CALL_N")
    net_label(draw, mm(296), mm(114), "KEY_PTT_N")

    led_y1 = mm(195)
    for idx, name in enumerate(["LED1\nPWR", "LED2\nCALL", "LED3\nTX", "LED4\nFAULT"]):
        x = mm(35) + idx * mm(32)
        block(draw, (x, led_y1, x + mm(26), led_y1 + mm(35)), name, "")
    rect(draw, (mm(168), led_y1, mm(224), led_y1 + mm(35)), width=2)
    center_text(draw, (mm(196), led_y1 + 17), "BZ1 / Q50", FONT_S)
    connection(draw, (mm(224), led_y1 + 17), (mm(240), led_y1 + 17), width=2)
    net_label(draw, mm(176), led_y1 - 18, "LED_* / BUZZER_EN")

    # service/status labels around MCU
    net_label(draw, mm(214), mm(52), "+3V3_DIG")
    net_label(draw, mm(214), mm(70), "VBAT_ADC")
    net_label(draw, mm(214), mm(88), "PWR_GOOD")
    net_label(draw, mm(214), mm(106), "FAULT_IN")
    net_label(draw, mm(214), mm(124), "LINK_PRESENT")
    return img


def principal_audio_optics():
    img, draw, frame, content = sheet("Схема электрическая принципиальная", "ПС.Э3.2", "Э3", 4, 5)
    x1, y1, x2, y2 = content
    center_text(draw, ((x1 + x2) // 2, y1 + 20), "ПРИНЦИПИАЛЬНАЯ СХЕМА. АУДИО И ОПТИКА", FONT_H)

    block(draw, (mm(30), mm(62), mm(68), mm(104)), "J20", "MIC")
    block(draw, (mm(76), mm(62), mm(114), mm(104)), "D20", "ESD")
    block(draw, (mm(124), mm(56), mm(188), mm(110)), "U20A", "Предусилитель\nHPF / LPF")
    block(draw, (mm(200), mm(56), mm(270), mm(110)), "U21", "Кодек\nADC / DAC")
    block(draw, (mm(284), mm(56), mm(352), mm(110)), "U40", "TX тракт")
    block(draw, (mm(364), mm(56), mm(404), mm(110)), "J40", "TX\nFIBER")

    connection(draw, (mm(68), mm(83)), (mm(76), mm(83)), width=2)
    connection(draw, (mm(114), mm(83)), (mm(124), mm(83)), width=2)
    connection(draw, (mm(188), mm(83)), (mm(200), mm(83)), width=2)
    connection(draw, (mm(270), mm(83)), (mm(284), mm(83)), width=2)
    connection(draw, (mm(352), mm(83)), (mm(364), mm(83)), width=2)
    net_label(draw, mm(134), mm(43), "MIC_PRE_OUT")
    net_label(draw, mm(218), mm(43), "CODEC_ADC_IN")
    net_label(draw, mm(294), mm(43), "TX_DATA / OPT_TX_EN")

    block(draw, (mm(364), mm(138), mm(404), mm(192)), "J41", "RX\nFIBER")
    block(draw, (mm(284), mm(138), mm(352), mm(192)), "U41", "RX тракт")
    block(draw, (mm(200), mm(138), mm(270), mm(192)), "U21", "Кодек\nDAC")
    block(draw, (mm(124), mm(138), mm(188), mm(192)), "U30", "Усилитель\nНЧ")
    block(draw, (mm(30), mm(138), mm(98), mm(192)), "J30", "Громко-\nговоритель")

    connection(draw, (mm(364), mm(165)), (mm(352), mm(165)), width=2)
    connection(draw, (mm(284), mm(165)), (mm(270), mm(165)), width=2)
    connection(draw, (mm(200), mm(165)), (mm(188), mm(165)), width=2)
    connection(draw, (mm(124), mm(165)), (mm(98), mm(165)), width=2)
    net_label(draw, mm(290), mm(195), "RX_DATA / LINK_PRESENT")
    net_label(draw, mm(204), mm(195), "CODEC_DAC_OUT")
    net_label(draw, mm(122), mm(195), "SPK_OUT")

    block(draw, (mm(208), mm(214), mm(280), mm(252)), "U10", "Контроллер")
    connection(draw, (mm(244), mm(214)), (mm(244), mm(192)), width=2)
    connection(draw, (mm(244), mm(110)), (mm(244), mm(214)), width=2)
    net_label(draw, mm(248), mm(120), "AUDIO_IF")
    net_label(draw, mm(248), mm(172), "AMP_EN")
    return img


def logic_sheet():
    img, draw, frame, content = sheet("Логика работы и переходы состояний", "ПС.ТЛ1", "ТЛ", 5, 5)
    x1, y1, x2, y2 = content
    center_text(draw, ((x1 + x2) // 2, y1 + 20), "ТАБЛИЦА ЛОГИКИ РАБОТЫ ИЗДЕЛИЯ", FONT_H)

    # main state machine blocks
    block(draw, (mm(38), mm(58), mm(105), mm(92)), "S0", "ВЫКЛЮЧЕНО")
    block(draw, (mm(140), mm(58), mm(207), mm(92)), "S1", "ИНИЦИАЛИЗАЦИЯ")
    block(draw, (mm(242), mm(58), mm(309), mm(92)), "S2", "ОЖИДАНИЕ")
    block(draw, (mm(344), mm(58), mm(402), mm(92)), "S3", "ВЫЗОВ")
    block(draw, (mm(242), mm(108), mm(309), mm(142)), "S4", "ПЕРЕДАЧА")
    block(draw, (mm(344), mm(108), mm(402), mm(142)), "S5", "ПРИЁМ")
    block(draw, (mm(242), mm(158), mm(309), mm(192)), "S6", "АВАРИЯ")
    block(draw, (mm(344), mm(158), mm(402), mm(192)), "S7", "НИЗКИЙ\nЗАРЯД")

    arrow(draw, (mm(105), mm(75)), (mm(140), mm(75)), width=2)
    arrow(draw, (mm(207), mm(75)), (mm(242), mm(75)), width=2)
    arrow(draw, (mm(309), mm(75)), (mm(344), mm(75)), width=2)
    arrow(draw, (mm(373), mm(92)), (mm(373), mm(108)), width=2)
    arrow(draw, (mm(275), mm(92)), (mm(275), mm(108)), width=2)
    arrow(draw, (mm(309), mm(125)), (mm(344), mm(125)), width=2)
    arrow(draw, (mm(344), mm(136)), (mm(309), mm(175)), width=2)
    arrow(draw, (mm(275), mm(142)), (mm(275), mm(158)), width=2)
    arrow(draw, (mm(373), mm(142)), (mm(373), mm(158)), width=2)
    net_label(draw, mm(116), mm(62), "ПОДАЧА ПИТАНИЯ")
    net_label(draw, mm(218), mm(62), "PWR_GOOD")
    net_label(draw, mm(318), mm(62), "KEY_CALL")
    net_label(draw, mm(378), mm(98), "REMOTE_ANSWER")
    net_label(draw, mm(214), mm(113), "KEY_PTT")
    net_label(draw, mm(312), mm(113), "REMOTE_TX")
    net_label(draw, mm(318), mm(166), "LINK_FAULT / LOW_BAT")

    # table section
    tx1, ty1, tx2, ty2 = mm(38), mm(200), mm(402), mm(226)
    rect(draw, (tx1, ty1, tx2, ty2), width=2)
    real_cols = [tx1, mm(78), mm(150), mm(258), mm(344), mm(402)]
    for x in real_cols[1:-1]:
        line(draw, (x, ty1, x, ty2), width=1)
    for y in [ty1 + mm(6), ty1 + mm(11), ty1 + mm(16), ty1 + mm(21)]:
        line(draw, (tx1, y, tx2, y), width=1)
    headers = ["Состояние", "Условие входа", "Действие контроллера", "Индикация", "Переход"]
    x_positions = [(tx1 + mm(78)) // 2, (mm(78) + mm(150)) // 2, (mm(150) + mm(258)) // 2, (mm(258) + mm(344)) // 2, (mm(344) + mm(402)) // 2]
    for xp, text in zip(x_positions, headers):
        center_text(draw, (xp, ty1 + mm(3)), text, FONT_XS)

    rows = [
        ["S2 Ожидание", "LINK_PRESENT=1", "Опрос клавиш, контроль линии", "PWR", "S3/S4/S6/S7"],
        ["S3 Вызов", "KEY_CALL=1", "Передача команды вызова", "CALL", "S4/S5/S6"],
        ["S4 Передача", "KEY_PTT=1", "TX_ENABLE=1, AMP_EN=0", "TX", "S2/S6/S7"],
        ["S5 Приём", "REMOTE_TX=1", "TX_ENABLE=0, AMP_EN=1", "CALL/TX", "S2/S6/S7"],
    ]
    row_y = [ty1 + mm(6), ty1 + mm(11), ty1 + mm(16), ty1 + mm(21)]
    col_boxes = [(tx1, mm(78)), (mm(78), mm(150)), (mm(150), mm(258)), (mm(258), mm(344)), (mm(344), mm(402))]
    for ry, row in zip(row_y, rows):
        for (cx1, cx2), text in zip(col_boxes, row):
            text_box(draw, (cx1 + 2, ry + 1, cx2 - 2, ry + mm(5) - 1), text, FONT_XS, padding=1, spacing=1)

    return img


def save_outputs(images):
    png_paths = []
    for filename, image in images:
        path = OUT_DIR / filename
        image.save(path, format="PNG", optimize=True)
        png_paths.append(path)
    pdf_path = OUT_DIR / "17_21_eskd_scheme_set_v2.pdf"
    rgb_images = [image.convert("RGB") for _, image in images]
    rgb_images[0].save(pdf_path, save_all=True, append_images=rgb_images[1:])
    return png_paths, pdf_path


def main():
    images = [
        ("17_eskd_e1_structural_scheme_v2.png", structural_sheet()),
        ("18_eskd_e2_functional_scheme_v2.png", functional_sheet()),
        ("19_eskd_e3_power_control_v2.png", principal_power_control()),
        ("20_eskd_e3_audio_optics_v2.png", principal_audio_optics()),
        ("21_eskd_logic_state_table_v2.png", logic_sheet()),
    ]
    png_paths, pdf_path = save_outputs(images)
    print("Generated:")
    for path in png_paths:
        print(path)
    print(pdf_path)


if __name__ == "__main__":
    main()
