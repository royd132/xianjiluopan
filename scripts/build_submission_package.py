from __future__ import annotations

import hashlib
import math
import os
import shutil
import sys
import textwrap
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "deliverables" / "初赛提交包"
SCREENSHOTS = PACKAGE / "screenshots"
PDF_PATH = PACKAGE / "先机罗盘_初赛方案说明书.pdf"
TUTORIAL_PDF_PATH = PACKAGE / "先机罗盘_完整使用演示教程.pdf"
ZIP_PATH = ROOT / "deliverables" / "先机罗盘_菜菜唠唠_初赛提交包.zip"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

BLUE = "#2563EB"
NAVY = "#142130"
INK = "#172033"
MUTED = "#667085"
PALE = "#F5F7F4"
GREEN = "#159E78"
AMBER = "#D99518"
PURPLE = "#7656C9"
WHITE = "#FFFFFF"
LINE = "#DDE3EA"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=None, radius=16, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def fit_lines(draw, text, fnt, max_width):
    lines = []
    for raw in text.split("\n"):
        current = ""
        for ch in raw:
            trial = current + ch
            if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = ch
        lines.append(current)
    return lines


def draw_centered(draw, text, box, fnt, fill=INK, spacing=10):
    x1, y1, x2, y2 = box
    lines = fit_lines(draw, text, fnt, x2 - x1)
    heights = [draw.textbbox((0, 0), line, font=fnt)[3] for line in lines]
    total = sum(heights) + spacing * (len(lines) - 1)
    y = y1 + (y2 - y1 - total) / 2
    for line, h in zip(lines, heights):
        w = draw.textbbox((0, 0), line, font=fnt)[2]
        draw.text((x1 + (x2 - x1 - w) / 2, y), line, font=fnt, fill=fill)
        y += h + spacing


def arrow(draw, start, end, fill=BLUE, width=4):
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for delta in (2.6, -2.6):
        p = (end[0] + 14 * math.cos(angle + delta), end[1] + 14 * math.sin(angle + delta))
        draw.line([end, p], fill=fill, width=width)


def base_canvas(title, eyebrow):
    img = Image.new("RGB", (1600, 900), PALE)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1600, 108), fill=NAVY)
    draw.text((70, 24), eyebrow, font=font(22, True), fill="#8FB4FF")
    draw.text((70, 54), title, font=font(36, True), fill=WHITE)
    draw.text((1430, 40), "先机罗盘", font=font(23, True), fill=WHITE)
    return img, draw


def build_architecture():
    img, draw = base_canvas("可审计、可恢复、可热更新的多 Agent 决策架构", "TECHNICAL ARCHITECTURE")
    layers = [
        (142, 228, "交互层", "React 决策工作台  ·  SSE 进度  ·  证据下钻  ·  人工复核", BLUE),
        (260, 346, "服务层", "FastAPI  ·  任务 API  ·  导出与分享  ·  信号快照", GREEN),
        (378, 500, "运行时", "共享黑板  ·  Schema 闸门  ·  Checkpoint  ·  局部重算", PURPLE),
        (532, 676, "Agent 层", "Collector   Review   Market   Supply Chain   Decision   Safety", AMBER),
        (708, 830, "数据与模型", "Qwen Adapter  ·  Amazon Reviews  ·  Olist  ·  UN Comtrade  ·  ECB  ·  GSCPI  ·  LSCI", "#3D7C75"),
    ]
    for y1, y2, label, content, accent in layers:
        rounded(draw, (190, y1, 1410, y2), WHITE, LINE, 12, 2)
        draw.rectangle((190, y1, 204, y2), fill=accent)
        draw.text((230, y1 + 25), label, font=font(25, True), fill=INK)
        draw.text((430, y1 + 29), content, font=font(21), fill=MUTED)
        if y2 < 830:
            arrow(draw, (800, y2 + 3), (800, y2 + 25), fill="#98A2B3", width=3)

    rounded(draw, (30, 290, 175, 690), "#ECF3FF", "#BFD2FF", 14, 2)
    draw_centered(draw, "HARNESS\nTrace\n权限策略\n组件快照\n热更新\n版本回滚", (44, 310, 161, 670), font(18, True), BLUE, 18)
    rounded(draw, (1425, 290, 1570, 690), "#EAF8F3", "#BDE6D7", 14, 2)
    draw_centered(draw, "治理闭环\n证据校验\n人工反馈\nValidation\nHoldout\n人工激活", (1439, 310, 1556, 670), font(18, True), GREEN, 18)
    draw.text((190, 855), "设计原则：模型做语义理解；代码做数值、时间、证据与权限判断。", font=font(20), fill=MUTED)
    path = PACKAGE / "03_技术架构图.png"
    img.save(path, quality=95)
    return path


def build_workflow():
    img, draw = base_canvas("从问题到四张决策卡，再到变化触发重算", "AI AGENT WORKFLOW")
    steps = [
        ("01", "任务输入", "品类 × 国家 × 数据模式"),
        ("02", "能力检查", "真实数据不足则拒绝"),
        ("03", "数据采集", "价格 / 评论 / 贸易 / 汇率 / 物流"),
        ("04", "并行分析", "Review / Market / Supply Chain"),
        ("05", "决策编译", "选品 / 定价 / 竞争 / 人群"),
        ("06", "安全门禁", "证据数 / 新鲜度 / 失败条件"),
        ("07", "人工复核", "采纳 / 待议 / 驳回"),
        ("08", "信号监控", "阈值触发受影响卡重算"),
    ]
    positions = [(90, 180), (430, 180), (770, 180), (1110, 180), (1110, 510), (770, 510), (430, 510), (90, 510)]
    accents = [BLUE, BLUE, GREEN, GREEN, AMBER, PURPLE, PURPLE, GREEN]
    for idx, ((num, title, body), (x, y), accent) in enumerate(zip(steps, positions, accents)):
        rounded(draw, (x, y, x + 290, y + 190), WHITE, LINE, 12, 2)
        rounded(draw, (x + 20, y + 20, x + 74, y + 64), accent, None, 10)
        draw.text((x + 31, y + 28), num, font=font(18, True), fill=WHITE)
        draw.text((x + 20, y + 84), title, font=font(28, True), fill=INK)
        for li, line in enumerate(fit_lines(draw, body, font(18), 245)):
            draw.text((x + 20, y + 132 + li * 26), line, font=font(18), fill=MUTED)
        if idx < 3:
            arrow(draw, (x + 290, y + 95), (positions[idx + 1][0] - 16, y + 95), fill="#7A8AA0", width=4)
        elif idx == 3:
            arrow(draw, (x + 145, y + 190), (x + 145, positions[idx + 1][1] - 16), fill="#7A8AA0", width=4)
        elif idx < 7:
            arrow(draw, (x, y + 95), (positions[idx + 1][0] + 306, y + 95), fill="#7A8AA0", width=4)
    draw.arc((30, 120, 1550, 835), start=145, end=215, fill=GREEN, width=5)
    arrow(draw, (75, 455), (80, 380), fill=GREEN, width=5)
    draw.text((575, 430), "共享黑板 + Trace + Checkpoint", font=font(24, True), fill=BLUE)
    draw.text((90, 840), "闭环不是自动改写线上策略：失败案例需经过双分区回放，并由人确认激活。", font=font(20), fill=MUTED)
    path = PACKAGE / "04_AI工作流图.png"
    img.save(path, quality=95)
    return path


def register_pdf_fonts():
    pdfmetrics.registerFont(TTFont("YaHei", str(FONT_REGULAR), subfontIndex=0))
    pdfmetrics.registerFont(TTFont("YaHeiBold", str(FONT_BOLD), subfontIndex=0))


def pdf_header_footer(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(colors.HexColor(LINE))
        canvas.line(18 * mm, 16 * mm, 192 * mm, 16 * mm)
        canvas.setFont("YaHei", 8)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(18 * mm, 10 * mm, "菜菜唠唠 · 先机罗盘 · 场景三 AI 市场洞察")
        canvas.drawRightString(192 * mm, 10 * mm, str(doc.page))
    canvas.restoreState()


def build_pdf(arch_path, flow_path):
    register_pdf_fonts()
    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=21 * mm, title="先机罗盘初赛方案说明书",
        author="菜菜唠唠",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontName="YaHeiBold", fontSize=26, leading=36, textColor=colors.HexColor(INK), alignment=TA_CENTER, spaceAfter=8)
    subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontName="YaHei", fontSize=12, leading=20, textColor=colors.HexColor(MUTED), alignment=TA_CENTER)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="YaHeiBold", fontSize=18, leading=25, textColor=colors.HexColor(INK), spaceBefore=8, spaceAfter=9)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="YaHeiBold", fontSize=13, leading=19, textColor=colors.HexColor(BLUE), spaceBefore=7, spaceAfter=5)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="YaHei", fontSize=9.2, leading=15, textColor=colors.HexColor(INK), spaceAfter=5)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=12, textColor=colors.HexColor(MUTED))
    callout = ParagraphStyle("callout", parent=body, fontName="YaHeiBold", fontSize=12, leading=20, textColor=colors.HexColor(BLUE), alignment=TA_CENTER, borderColor=colors.HexColor("#BFD2FF"), borderWidth=1, borderPadding=10, backColor=colors.HexColor("#EEF4FF"), spaceBefore=8, spaceAfter=10)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=13, firstLineIndent=-9, bulletIndent=2, spaceAfter=3)

    def P(txt, style=body):
        return Paragraph(txt, style)

    def bullets(items):
        return [P("• " + item, bullet) for item in items]

    def table(data, widths=None, header=True):
        prepared = [[P(str(c), small if r else ParagraphStyle("th", parent=small, fontName="YaHeiBold", textColor=colors.white)) for c in row] for r, row in enumerate(data)]
        t = Table(prepared, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("GRID", (0, 0), (-1, -1), .4, colors.HexColor(LINE)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        for r in range(1, len(data)):
            cmds.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#F7F9FB" if r % 2 == 0 else WHITE)))
        t.setStyle(TableStyle(cmds))
        return t

    story = []
    story += [Spacer(1, 34 * mm), P("先机罗盘", title), P("Foresight Compass", subtitle), Spacer(1, 8 * mm)]
    story += [P("用可核查数据回答：一个新品是否值得进入某个海外市场？", callout)]
    story += [Spacer(1, 12 * mm), P("场景三 · AI 市场洞察", subtitle), Spacer(1, 3 * mm)]
    story += [table([
        ["团队", "队长及联系方式", "队员"],
        ["菜菜唠唠", "邹柏良 · 13204942689", "周展序、向顺、庞佳轩、董志兵"],
    ], [42 * mm, 58 * mm, 74 * mm])]
    story += [Spacer(1, 34 * mm), P("提交版本 v1.0 · 2026-08-21", subtitle), P("代码仓库 github.com/royd132/xianjiluopan", subtitle), PageBreak()]

    story += [P("01 具体业务问题", h1)]
    story += [P("跨境卖家真正高风险的时刻，是付样品费、开模、下首批订单或投入广告之前。数据不少，但价格、评论、贸易、汇率和供应链信息相互割裂，最后仍常靠经验拍板。", body)]
    story += [P("本方案聚焦一个可衡量的决策", h2), P("一个新品是否值得进入某个海外市场，以及在备货前应该先验证什么？", callout)]
    story += [P("五个业务断点", h2)] + bullets([
        "数据分散、多语言且口径不同，人工研究需要数天；",
        "通用 AI 能给建议，但经常无法回指原始评论和数值来源；",
        "历史、跨市场与实时信息容易混用，导致错误确定性；",
        "报告停留在描述趋势，没有给出下一步验证动作；",
        "市场变化后结论不会主动失效，也缺少停止条件。",
    ])
    story += [P("目标用户", h2)] + bullets([
        "1-5 人、没有本地研究团队的中小跨境卖家；",
        "准备进入陌生国家的平台卖家和工厂型卖家；",
        "需要批量交付研究的代运营与出海服务商。",
    ])
    story += [P("一句话定位", h2), P("先机罗盘把分散的市场数据编译成可验证的选品、定价、竞争和种子人群决策，让卖家在不可逆投入前先验证、再投入。", body), PageBreak()]

    story += [P("02 产品功能", h1)]
    feature_rows = [["核心功能", "用户得到什么", "可信机制"],
        ["新品进入决策", "输入品类与国家，得到场景能力边界", "Real / Hybrid / Mock 明示；数据不足直接拒绝"],
        ["四类决策卡", "选品、定价、竞争、种子人群的具体动作", "证据、置信度、有效期、失败条件、人工状态"],
        ["多语言痛点", "从原语评论发现“喜欢但是”的真实缺陷", "模型返回记录 ID，代码取回原文"],
        ["变化触发", "汇率、物流、价格变化后局部更新建议", "数据源级 SLA、阈值、失效策略"],
        ["受控演进", "把采纳/驳回沉淀为可验证的策略改进", "Validation / Holdout 回放 + 人工激活"],
    ]
    story += [table(feature_rows, [35 * mm, 66 * mm, 73 * mm]), Spacer(1, 6 * mm)]
    story += [P("真实任务原型", h2), RLImage(str(SCREENSHOTS / "01_研究入口.png"), width=174 * mm, height=92 * mm), P("图 1：巴西 × 宠物自动喂食器真实任务。页面显示数据模式、四张决策卡及市场监控状态。", small), PageBreak()]

    story += [P("03 从洞察到行动", h1), RLImage(str(SCREENSHOTS / "03_机会与风险.png"), width=174 * mm, height=92 * mm), P("图 2：原语痛点、供应链信号与证据入口。产品不是排行榜，而是把数据编译成验证动作。", small)]
    story += [P("四张卡回答四个经营问题", h2)] + bullets([
        "选品方向：优先验证哪个差异化问题；",
        "定价策略：以什么价格区间开始测试，还缺哪些成本；",
        "竞争打法：应该审计哪个表达空位；",
        "种子人群：先找谁、在哪里找、如何测试意向。",
    ])
    story += [P("每张卡还必须回答：证据是什么、结论能维持多久、什么变化会推翻它、谁复核过。", callout), PageBreak()]

    story += [P("04 AI Agent 与工作流", h1), RLImage(str(flow_path), width=174 * mm, height=98 * mm), P("图 3：多 Agent 研究流与信号触发闭环。", small)]
    story += [P("AI 能力落地", h2), table([
        ["能力", "实现方式", "业务作用"],
        ["多语言理解", "Qwen 结构化输出", "聚类英语、葡语等评论中的隐性痛点"],
        ["Grounding", "模型仅返回 review ID", "原文由代码取回，防止伪引用"],
        ["多 Agent", "Collector / Review / Market / Supply / Decision / Safety", "把复杂研究拆成可追踪专业角色"],
        ["确定性计算", "Python 规则、Schema 和统计", "数值、阈值、时间和证据校验不交给模型猜"],
    ], [35 * mm, 62 * mm, 77 * mm]), PageBreak()]

    story += [P("05 技术架构与创新", h1), RLImage(str(arch_path), width=174 * mm, height=98 * mm), P("图 4：Runtime、Harness、Agent、Provider 与治理闭环。", small)]
    story += [P("核心创新不是简单堆叠 Agent", h2)] + bullets([
        "共享黑板只允许结构化 Artifact 交换，降低对话漂移；",
        "Harness 记录 Trace、Checkpoint、工具权限和组件快照；",
        "Provider 可热更新，运行中的任务锁定旧版本，新任务采用新版本；",
        "失败反馈不能直接改线上策略，候选策略必须通过双分区回放；",
        "数据与模型解耦，后续可替换平台接口和模型供应商。",
    ])
    story += [PageBreak()]

    story += [P("06 实时性与跨境特有需求", h1)]
    story += [P("实时性不是给所有数据贴上“实时”标签，而是为每类信号建立不同的新鲜度合同。系统分别记录数据发生时间 observed_at 与读取时间 collected_at，并在超出 SLA 时降级、告警或阻止高风险建议。", body)]
    story += [table([
        ["数据类型", "生产目标", "接入与更新", "过期后的处理"],
        ["汇率", "秒级至分钟级", "WebSocket / 高频轮询", "重算利润与价格卡"],
        ["竞品价格/库存", "5-30 分钟", "平台授权 API / Webhook", "标红并重算竞争卡"],
        ["评论/评分", "15-60 分钟", "增量 API / 游标轮询", "更新痛点聚类与置信度"],
        ["物流/供应链", "小时至日级", "承运商 API / 指数源", "更新交期与成本假设"],
        ["海关贸易", "官方发布周期", "批量增量同步", "作为结构性基线，不冒充实时"],
    ], [30 * mm, 31 * mm, 55 * mm, 58 * mm])]
    story += [Spacer(1, 5 * mm), P("架构已为后续接口接入预留 Provider 协议、幂等、重试、熔断、断流告警和局部重算机制。当前原型实现手动市场快照及触发计数，尚未把所有第三方接口包装成已完成能力。", callout), PageBreak()]

    story += [P("07 业务价值与验证计划", h1)]
    story += [table([
        ["指标", "传统方式", "首轮试点目标"],
        ["单品类 × 单市场首版研究", "2-3 个工作日", "60-90 秒形成首版四卡"],
        ["核心建议可追溯率", "依赖人工整理", "100% 关联证据对象"],
        ["备货前验证", "经常直接投入", "30 份意向测试 + 5 次深访"],
        ["结论更新", "人工重做", "阈值触发局部重算"],
        ["错误建议定位", "依赖聊天记录", "关联证据、Agent、组件版本和反馈"],
    ], [57 * mm, 50 * mm, 67 * mm])]
    story += [P("试点设计", h2)] + bullets([
        "招募 10 位中小卖家，覆盖 3 个品类和 3 个目标市场；",
        "对比人工研究耗时、卡片采纳率、证据覆盖率与验证完成率；",
        "重点统计系统帮助停止了多少证据不足的项目，而不只统计推荐数量；",
        "所有经营效果均作为待验证目标，不包装成既成商业成果。",
    ])
    story += [P("评审维度对应", h2), table([
        ["业务价值", "创新性", "可行性", "技术思路"],
        ["减少错误备货与无效投放", "四卡编译、证据回指、反向条件、受控演进", "真实数据原型、23 项测试、双端 CI", "多 Agent + Harness + Evidence Schema + Event Runtime"],
    ], [41 * mm, 48 * mm, 40 * mm, 45 * mm]), PageBreak()]

    story += [P("08 当前成果与边界", h1)]
    story += [P("已实现", h2)] + bullets([
        "React 决策工作台、移动端适配、FastAPI / SSE 和六类 Agent；",
        "Mock / Hybrid / Real 数据合同、场景能力矩阵和真实模式拒绝；",
        "Amazon Reviews、Olist、UN Comtrade、ECB、GSCPI、LSCI 与 Qwen 真实链路；",
        "证据时间、适用范围、新鲜度门禁、导出分享和市场快照；",
        "Trace、Checkpoint、热更新、组件快照、回滚和策略级受控演进；",
        "23 项自动化测试与 GitHub Actions。",
    ])
    story += [P("明确边界", h2)] + bullets([
        "当前竞品 listing 的授权实时接口尚未接入；",
        "后台定时调度、全量市场覆盖和通知投递属于下一阶段；",
        "不会自动采购或调价；高风险动作始终保留人工确认；",
        "历史快照和宏观指数会按其真实观察周期标识。",
    ])
    story += [RLImage(str(SCREENSHOTS / "05_进化中心.png"), width=174 * mm, height=92 * mm), P("图 5：可核查证据与策略演进中心。候选策略经过回放验证后仍需人工激活。", small)]
    story += [Spacer(1, 5 * mm), P("仓库：https://github.com/royd132/xianjiluopan", callout)]

    doc.build(story, onFirstPage=pdf_header_footer, onLaterPages=pdf_header_footer)
    return PDF_PATH


def build_tutorial_pdf():
    source_path = PACKAGE / "02_完整使用演示教程.md"
    register_pdf_fonts()
    doc = SimpleDocTemplate(
        str(TUTORIAL_PDF_PATH), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=21 * mm, title="先机罗盘完整使用演示教程",
        author="菜菜唠唠",
    )
    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle("tutorial-cover", parent=styles["Title"], fontName="YaHeiBold", fontSize=25, leading=36, textColor=colors.HexColor(INK), alignment=TA_CENTER)
    cover_subtitle = ParagraphStyle("tutorial-cover-sub", parent=styles["Normal"], fontName="YaHei", fontSize=11, leading=19, textColor=colors.HexColor(MUTED), alignment=TA_CENTER)
    h1 = ParagraphStyle("tutorial-h1", parent=styles["Heading1"], fontName="YaHeiBold", fontSize=17, leading=24, textColor=colors.HexColor(INK), spaceBefore=9, spaceAfter=7, keepWithNext=True)
    h2 = ParagraphStyle("tutorial-h2", parent=styles["Heading2"], fontName="YaHeiBold", fontSize=12.5, leading=18, textColor=colors.HexColor(BLUE), spaceBefore=7, spaceAfter=4, keepWithNext=True)
    body = ParagraphStyle("tutorial-body", parent=styles["BodyText"], fontName="YaHei", fontSize=9, leading=14.5, textColor=colors.HexColor(INK), spaceAfter=4)
    small = ParagraphStyle("tutorial-small", parent=body, fontSize=7.8, leading=12, textColor=colors.HexColor(MUTED))
    bullet = ParagraphStyle("tutorial-bullet", parent=body, leftIndent=14, firstLineIndent=-9, bulletIndent=2, spaceAfter=2.5)
    quote = ParagraphStyle("tutorial-quote", parent=body, fontName="YaHeiBold", fontSize=10.5, leading=17, textColor=colors.HexColor(BLUE), borderColor=colors.HexColor("#BFD2FF"), borderWidth=1, borderPadding=8, backColor=colors.HexColor("#EEF4FF"), spaceBefore=5, spaceAfter=7)
    code = ParagraphStyle("tutorial-code", parent=body, fontName="YaHei", fontSize=8, leading=13, textColor=colors.HexColor("#E7EEF8"), backColor=colors.HexColor(NAVY), borderPadding=7, leftIndent=4, rightIndent=4, spaceBefore=3, spaceAfter=6)
    th = ParagraphStyle("tutorial-th", parent=small, fontName="YaHeiBold", textColor=colors.white)

    def P(value, style=body):
        safe = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = safe.replace("**", "")
        safe = safe.replace("`", "")
        return Paragraph(safe, style)

    def make_table(rows):
        columns = max(len(row) for row in rows)
        prepared = []
        for row_index, row in enumerate(rows):
            padded = row + [""] * (columns - len(row))
            prepared.append([P(cell, th if row_index == 0 else small) for cell in padded])
        available = 174 * mm
        widths = [available / columns] * columns
        result = Table(prepared, colWidths=widths, repeatRows=1, hAlign="LEFT")
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
            ("GRID", (0, 0), (-1, -1), .4, colors.HexColor(LINE)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for row_index in range(1, len(rows)):
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F7F9FB" if row_index % 2 == 0 else WHITE)))
        result.setStyle(TableStyle(commands))
        return result

    story = [Spacer(1, 35 * mm), P("先机罗盘", cover_title), P("完整使用演示教程", cover_title), Spacer(1, 8 * mm)]
    story += [P("从启动环境到完成一项可核查的跨境市场进入决策", quote), Spacer(1, 12 * mm)]
    story += [P("团队：菜菜唠唠", cover_subtitle), P("主案例：宠物自动喂食器 × 巴西", cover_subtitle), P("版本：v1.0 · 2026-08-21", cover_subtitle), Spacer(1, 38 * mm)]
    story += [P("项目仓库 github.com/royd132/xianjiluopan", cover_subtitle), PageBreak()]

    lines = source_path.read_text(encoding="utf-8").splitlines()
    index = 0
    paragraph_buffer = []

    def flush_paragraph():
        if paragraph_buffer:
            story.append(P(" ".join(paragraph_buffer), body))
            paragraph_buffer.clear()

    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if index == 0 and stripped.startswith("# "):
            index += 1
            continue
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        if stripped.startswith("```"):
            flush_paragraph()
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            escaped_code = "<br/>".join(
                line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") or " "
                for line in code_lines
            )
            story.append(Paragraph(escaped_code, code))
            index += 1
            continue
        if stripped.startswith("![") and "](" in stripped and stripped.endswith(")"):
            flush_paragraph()
            alt = stripped[2:stripped.index("](")]
            relative = stripped[stripped.index("](") + 2:-1]
            image_path = PACKAGE / relative
            with Image.open(image_path) as preview:
                ratio = preview.height / preview.width
            width = 174 * mm
            height = min(width * ratio, 96 * mm)
            story.append(RLImage(str(image_path), width=width, height=height))
            story.append(P(f"图：{alt}", small))
            index += 1
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = []
            for table_line in table_lines:
                cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                if cells and all(set(cell) <= {"-", ":"} for cell in cells):
                    continue
                rows.append(cells)
            if rows:
                story.append(make_table(rows))
                story.append(Spacer(1, 3 * mm))
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            story.append(P(stripped[4:], h2))
            index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            story.append(P(stripped[3:], h1))
            index += 1
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                content = lines[index].strip()[1:].strip()
                if content:
                    quote_lines.append(content)
                index += 1
            story.append(P(" · ".join(quote_lines), quote))
            continue
        if stripped.startswith("- ") or (len(stripped) > 3 and stripped[0].isdigit() and ". " in stripped[:4]):
            flush_paragraph()
            content = stripped[2:] if stripped.startswith("- ") else stripped.split(". ", 1)[1]
            marker = "• " if stripped.startswith("- ") else stripped.split(". ", 1)[0] + ". "
            story.append(P(marker + content, bullet))
            index += 1
            continue
        paragraph_buffer.append(stripped)
        index += 1
    flush_paragraph()
    doc.build(story, onFirstPage=pdf_header_footer, onLaterPages=pdf_header_footer)
    return TUTORIAL_PDF_PATH


def build_manifest(files):
    lines = ["# 文件校验清单", "", "生成日期：2026-08-21", "", "| 文件 | SHA-256 | 大小 |", "|---|---|---:|"]
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"| {path.relative_to(PACKAGE).as_posix()} | `{digest}` | {path.stat().st_size:,} bytes |")
    manifest = PACKAGE / "文件校验清单.md"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def build_zip():
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                zf.write(path, Path("先机罗盘_菜菜唠唠_初赛提交包") / path.relative_to(PACKAGE))
    return ZIP_PATH


def main():
    PACKAGE.mkdir(parents=True, exist_ok=True)
    required = [SCREENSHOTS / f for f in ["01_研究入口.png", "02_决策摘要.png", "03_机会与风险.png", "04_证据链.png", "05_进化中心.png"]]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing screenshots: " + ", ".join(missing))
    arch = build_architecture()
    flow = build_workflow()
    pdf = build_pdf(arch, flow)
    tutorial_pdf = build_tutorial_pdf()
    source_files = [
        PACKAGE / "README_提交说明.md", PACKAGE / "01_初赛Idea提交稿.md", PACKAGE / "02_完整使用演示教程.md",
        arch, flow, pdf, tutorial_pdf, *required,
    ]
    manifest = build_manifest(source_files)
    package_zip = build_zip()
    print(f"PDF={pdf}")
    print(f"TUTORIAL={tutorial_pdf}")
    print(f"MANIFEST={manifest}")
    print(f"ZIP={package_zip}")


if __name__ == "__main__":
    main()
