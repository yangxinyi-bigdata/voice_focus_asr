"""生成双领夹麦录音的打印清单（HTML）和预填清单（manifest.tsv）。

    python scripts/make_recording_checklist.py --out-dir docs/experiments

录音内容来自 docs/experiments/lavalier_full_recording_plan.md 与 lavalier_round1_scripts.md。
"""

from __future__ import annotations

import argparse
import csv
import html
from dataclasses import dataclass, field
from pathlib import Path

A_ONLY = [
    "这家店我上个月来过一次，他们的招牌是酸菜鱼，一份大概八十八块，两个人吃刚好。你要是不能吃辣，可以让他们做成微辣。",
    "我下周三要去杭州出差，大概待四天，周六晚上回来。你要是有空，周日中午我们可以约在西单见面，我请你吃饭。",
    "张老师说那个报名表要在十五号之前交，需要贴一张两寸照片，还要写清楚联系电话。我明天顺路帮你一起交过去吧。",
]
B_ONLY = [
    "我觉得这里有点吵，刚才你说的那句话我没听清楚。能不能再说一遍，或者我们换到靠窗那边的位置坐。",
    "我今天上午去医院复查了，医生说恢复得还不错，下个月再去一次就行。最近睡得也比以前好多了。",
    "我想点一个清炒时蔬和一碗米饭，再要一壶大麦茶。服务员刚才说今天的红烧肉已经卖完了。",
]
ALTERNATING = [
    [
        ("A", "你想喝点什么，要不要来一杯热豆浆？"),
        ("B", "好啊，我不要加糖。"),
        ("A", "那我点两杯，再要一笼小笼包，八个的那种。"),
        ("B", "可以，我最近胃口一般，吃不了太多。"),
        ("A", "没关系，吃不完我们打包带走。"),
    ],
    [
        ("A", "你还记得小刘吗，就是以前住在三楼的那个。"),
        ("B", "记得，他后来搬到南京去了。"),
        ("A", "对，他下个月结婚，婚礼定在二十号，在他老家办。"),
        ("B", "那我们要不要一起过去？"),
        ("A", "我打算坐高铁去，大概三个半小时，你要去我帮你一起买票。"),
    ],
    [
        ("A", "嗯，这个汤有点咸了。"),
        ("B", "是吗，我倒觉得还行。"),
        ("A", "对，可能是我口味比较淡。你明天几点下班？"),
        ("B", "一般六点左右，不过明天可能要加班。"),
        ("A", "那我们改到周五晚上七点吧，还是在这家店门口见。"),
    ],
]
OVERLAP = [
    (
        "明天早上九点半在地铁站二号出口集合，记得带身份证，我们先去办手续，然后一起吃午饭。",
        "我昨天晚上看了一部电影，讲的是一个老人开车穿越沙漠的故事，结尾有点伤感。",
    ),
    (
        "这个月的房租我已经转给房东了，一共三千二，水电费下周再算，你到时候把你那一半转给我。",
        "我家楼下新开了一家面包店，每天早上七点开门，他们的全麦面包特别香。",
    ),
    (
        "妈妈说周末想来看看我们，大概星期六下午两点到，我去火车站接她，晚上一起在家吃饭。",
        "公司楼下的停车场最近在修，我这几天都是骑共享单车上班的，反而觉得挺方便。",
    ),
]
ENROLL_A = (
    "我平时周末喜欢去郊区爬山，早上六点多出门，路上买个包子和豆浆。山顶风景特别好，天气晴的时候能看到很远的水库。"
    "下山以后找个农家乐吃顿饭，一般下午四点前就能回到家，晚上再看会儿书，第二天上班也不觉得累。"
)
ENROLL_B = (
    "我最近在学做饭，先从简单的番茄炒蛋和青椒肉丝开始。一开始总是盐放多了，后来买了一个小量勺，味道就稳定多了。"
    "上个星期试着炖了一锅排骨汤，炖了两个小时，骨头都酥了。下一步打算学包饺子，听说和面最难掌握。"
)
BACKCHANNEL = (
    "我跟你说，上周末我去看了一套房子，在地铁站附近，走路大概十分钟。房子是两室一厅，朝南，采光挺好的。"
    "就是楼层有点高，在十八楼，电梯早上要排队。价格比我预想的贵了一点，中介说还可以再谈。"
    "我打算这周六再去看一次，顺便问问物业费是多少。"
)
INTERRUPT = [
    ("A", "我觉得我们下个月可以一起去成都玩几天，那边的火锅和"),
    ("B", "哎，下个月我可能要出差。"),
    ("A", "哦，那就再往后推一推，十一月也行，那边天气也不冷，我们可以顺便去看看熊猫。"),
]
NUMBERS = (
    "你记一下，他的电话是一三八，零零一二，三四五六。我们约的是十月十七号，星期五，下午三点二十。"
    "地址是朝阳区建国路八十八号，三单元，一零二室。定金交了五百，尾款还有两千三百八十块，月底之前付清就行。"
)

BEFORE_LEAVING = [
    "A 已签知情同意书",
    "两个发射器、接收器、充电盒充满电；户外场景带防风毛罩",
    "发射器贴标签：左 = 对方（A），右 = 我（B）",
    "两个发射器降噪关闭、增益相同；接收器为立体声模式",
    "语音备忘录音频质量为“无损”，并开启 iCloud 同步作为备份",
    "iPhone 开飞行模式或勿扰；存储空间充足",
    "iPhone“设置 → 辅助功能 → 音频与视觉 → 单声道音频”保持关闭，否则耳机回放时听不出左右",
    "带耳机（检查左右声道用）、卷尺、移动电源；手机装好分贝仪",
    "包间放噪声场景：蓝牙音箱和餐馆环境声素材已准备好",
]
TOPICS = [
    "点菜：推荐菜、忌口、辣度、人数、分量",
    "约时间地点：下次见面的日期、时间、地点，路线怎么走",
    "家人与健康：最近身体怎样，家里老人和孩子的情况",
    "工作：最近在忙什么项目，遇到了什么麻烦",
    "旅行：去过的地方，推荐的景点、酒店、交通方式",
    "购物：最近买了什么，价格多少，在哪里买的",
    "讲一件事：最近遇到的一件好笑或倒霉的事，完整讲下来",
    "指路：从这里怎么去某个地方，要换几次车",
    "中英混杂：手机 App、咖啡名、品牌名，例如“下载个 App”“来杯 latte”",
    "聊新闻或电视剧：复述最近看到的内容",
]
HEADPHONE_CHECK = (
    "耳机检查：回放第一条，A 说话时声音应主要在左耳，B 说话时主要在右耳；"
    "如果两边一样响，说明没录成立体声，先排查再继续。左耳听力弱时，可以把左右耳机对调再听一次。"
)

VARIABLE_FIELDS = {
    "距离0.6米": {"distance_m": "0.6"},
    "距离1.5米": {"distance_m": "1.5"},
    "桌角坐": {"seating": "corner"},
    "并排坐": {"seating": "side"},
    "边走边聊": {"seating": "walking"},
    "麦在胸口": {"mic_position": "chest"},
    "麦被遮住": {"mic_position": "covered"},
    "我大声": {"notes": "B 偏大声"},
    "噪声65分贝": {"notes": "音箱播放餐馆噪声约 65 dBA"},
    "噪声75分贝": {"notes": "音箱播放餐馆噪声约 75 dBA"},
    "降噪基础": {"nc": "basic"},
    "降噪强": {"nc": "strong"},
}


@dataclass
class Row:
    kind: str
    variant: str
    number: str
    hint: str
    target_text: str = ""
    user_text: str = ""


@dataclass
class Section:
    title: str
    location: str
    minutes: int
    setup: list[str]
    rows: list[Row] = field(default_factory=list)
    day: str = ""
    optional: bool = False


def short(text: str, n: int = 16) -> str:
    return text if len(text) <= n else text[:n] + "…"


def core(number: int, variant: str = "基准") -> list[Row]:
    i = number - 1
    alt = ALTERNATING[i]
    a_alt = "".join(t for s, t in alt if s == "A")
    b_alt = "".join(t for s, t in alt if s == "B")
    return [
        Row(
            "对方单说", variant, f"{number:02d}", f"A 读：{short(A_ONLY[i])}（B 不出声）", A_ONLY[i]
        ),
        Row(
            "我单说",
            variant,
            f"{number:02d}",
            f"B 读：{short(B_ONLY[i])}（A 不出声）",
            user_text=B_ONLY[i],
        ),
        Row("交替说", variant, f"{number:02d}", f"轮流读：{short(alt[0][1])}", a_alt, b_alt),
        Row(
            "同时说",
            variant,
            f"{number:02d}",
            f"同时读。A：{short(OVERLAP[i][0], 10)}；B：{short(OVERLAP[i][1], 10)}",
            OVERLAP[i][0],
            OVERLAP[i][1],
        ),
    ]


def core12(variant: str = "基准") -> list[Row]:
    rows = core(1, variant) + core(2, variant) + core(3, variant)
    order = ["对方单说", "我单说", "交替说", "同时说"]
    return sorted(rows, key=lambda r: (order.index(r.kind), r.number))


def core4(variant: str) -> list[Row]:
    return core(1, variant)


def floor(variant: str = "基准") -> Row:
    return Row("底噪", variant, "01", "两人都不说话，60 秒")


def edge_cases(e8_hint: str) -> list[Row]:
    a_int = "".join(t for s, t in INTERRUPT if s == "A")
    b_int = "".join(t for s, t in INTERRUPT if s == "B")
    return [
        Row("附和", "基准", "01", "A 读附和稿，B 在句间插“嗯”“对”“是吗”", BACKCHANNEL),
        Row("打断", "基准", "01", "按打断稿：A 说到一半 B 插话", a_int, b_int),
        Row("我大声", "基准", "01", "同时说第 2 段，B 明显大声", OVERLAP[1][0], OVERLAP[1][1]),
        Row("对方小声", "基准", "01", "A 压低声音读对方单说第 2 段，B 不出声", A_ONLY[1]),
        Row("对方转头", "基准", "01", "A 转向侧面读对方单说第 3 段，B 不出声", A_ONLY[2]),
        Row("杂音", "基准", "01", "笑、咳嗽、喝水、碰杯、筷子碰碗、摸麦、整理衣领；都不说话"),
        Row("第三人", "基准", "01", e8_hint),
        Row("数字", "基准", "01", "A 读数字稿，B 不出声", NUMBERS),
    ]


def monologue(topic: int) -> Row:
    return Row("长独白", "基准", f"话题{topic}", f"A 按话题卡 {topic} 连续讲 1–2 分钟")


def free(topic: int, minutes: int, variant: str = "基准") -> Row:
    return Row(
        "自由聊天",
        variant,
        f"话题{topic}",
        f"按话题卡 {topic} 自然聊天 {minutes} 分钟，可以随时插话",
    )


SCENE_SETUP = [
    "拍照：座位、两人位置、麦克风位置",
    "卷尺量两人嘴部距离：＿＿＿ 米",
    "分贝仪读 30 秒环境音量：＿＿＿ dBA",
    "场记：两人说“我是左声道 / 我是右声道”，B 报地点，拍手",
    "第一条录完用耳机回放：A 说话主要在左耳，B 说话主要在右耳，再继续",
]


def build_sections() -> list[Section]:
    quiet = Section(
        "安静包间：基准与声纹（茶馆包间、按小时租的共享会议室等，能关门、允许放音箱）",
        "安静包间",
        75,
        ["预订约 3 小时，确认可以在包间里用音箱放声音", *SCENE_SETUP],
        day="第一天上午",
    )
    quiet.rows = [
        floor(),
        Row("正式声纹", "基准", "A", "A 单独读 A 声纹稿，再自由讲 30 秒；B 不出声", ENROLL_A),
        Row(
            "正式声纹",
            "基准",
            "B",
            "B 单独读 B 声纹稿，再自由讲 30 秒；A 不出声",
            user_text=ENROLL_B,
        ),
        Row("快速声纹", "基准", "A", "A 说一句 5 秒左右的自我介绍"),
        Row("快速声纹", "基准", "B", "B 说一句 5 秒左右的自我介绍"),
        *core12(),
        *edge_cases("B 的手机放桌边 0.5 米，外放一段别人说话的录音；两人不出声"),
        monologue(7),
        free(1, 10),
    ]

    quiet_vars = Section(
        "安静包间：几何与佩戴变化（每项 4 段）",
        "安静包间",
        45,
        ["每换一项只改这一个条件，其余保持基准：面对面、1 米、领口、降噪关"],
        day="第一天上午",
    )
    for variant in ["距离0.6米", "距离1.5米", "桌角坐", "并排坐", "麦在胸口", "麦被遮住"]:
        quiet_vars.rows += core4(variant)
    quiet_vars.rows += [
        Row("我单说", "我大声", "01", f"B 大声读：{short(B_ONLY[0])}", user_text=B_ONLY[0]),
        Row(
            "交替说",
            "我大声",
            "01",
            "轮流读交替说第 1 段，B 大声",
            "".join(t for s, t in ALTERNATING[0] if s == "A"),
            "".join(t for s, t in ALTERNATING[0] if s == "B"),
        ),
    ]

    noise = Section(
        "包间放噪声：同一个包间，音箱在 1.5–2 米外播放餐馆环境声",
        "包间放噪声",
        60,
        ["音箱素材不含清楚人声", "用分贝仪把音量调到指定分贝再录", *SCENE_SETUP[3:]],
        day="第一天上午",
    )
    noise.rows = [
        floor("噪声65分贝"),
        *core12("噪声65分贝"),
        floor("噪声75分贝"),
        *core12("噪声75分贝"),
        *core4("噪声75分贝-降噪基础"),
        *core4("噪声75分贝-降噪强"),
        Row("邻桌说话", "基准", "01", "音箱改放一段多人对话录音；两人不出声，60 秒"),
    ]

    echo = Section(
        "空旷大厅：强回声对照（瓷砖、玻璃多，但人少安静，例如非营业时段的快餐店）",
        "空旷大厅",
        15,
        SCENE_SETUP,
        day="第一天下午",
        optional=True,
    )
    echo.rows = [floor(), *core4("基准")]

    def restaurant(title: str, location: str, day: str, topics: tuple[int, int]) -> Section:
        section = Section(title, location, 90, SCENE_SETUP, day=day)
        section.rows = [
            floor(),
            Row("快速声纹", "基准", "A", "A 说一句 5 秒左右的自我介绍"),
            Row("快速声纹", "基准", "B", "B 说一句 5 秒左右的自我介绍"),
            *core12(),
            *edge_cases("真实点菜：A 和服务员正常交流，照常录"),
            monologue(topics[0]),
            free(topics[1], 15),
            *core4("桌角坐"),
        ]
        section.rows[-4:] = [
            Row(r.kind, r.variant, r.number, r.hint + "（可选）", r.target_text, r.user_text)
            for r in section.rows[-4:]
        ]
        return section

    normal = restaurant(
        "普通餐馆（中等嘈杂；如在咖啡厅录，地点改为“咖啡厅”）", "普通餐馆", "第一天下午", (5, 2)
    )
    loud = restaurant("吵闹餐馆（火锅、烧烤、大排档，高峰期）", "吵闹餐馆", "第一天晚上", (8, 3))

    food_court = Section("美食广场或快餐店", "美食广场", 45, SCENE_SETUP, day="第二天")
    food_court.rows = [floor(), *core12(), free(4, 10)]

    street = Section(
        "街边户外（发射器装防风毛罩）",
        "街边",
        45,
        ["两个发射器装好防风毛罩", *SCENE_SETUP],
        day="第二天",
    )
    street.rows = [floor(), *core12(), free(6, 10)]

    car = Section("行驶中的车内", "车内", 30, SCENE_SETUP[2:], day="第二天", optional=True)
    car.rows = [floor(), *core4("基准"), free(9, 10)]

    walking = Section("并排边走边聊", "街边", 20, SCENE_SETUP[3:], day="第二天", optional=True)
    walking.rows = [free(10, 10, "边走边聊")]

    market = Section("菜市场", "菜市场", 30, SCENE_SETUP, day="第二天", optional=True)
    market.rows = [floor(), *core4("基准"), free(1, 5)]

    return [
        quiet,
        quiet_vars,
        noise,
        echo,
        normal,
        loud,
        food_court,
        street,
        car,
        walking,
        market,
    ]


def filename(location: str, row: Row) -> str:
    return f"{location}_{row.kind}_{row.variant}_{row.number}_第1遍"


def manifest_row(section: Section, row: Row) -> dict[str, str]:
    fields = {
        "file": filename(section.location, row) + ".m4a",
        "keep": "",
        "scene": section.title,
        "location": section.location,
        "case": row.kind,
        "target_channel": "left",
        "distance_m": "1.0",
        "seating": "face",
        "mic_position": "collar",
        "nc": "off",
        "noise_dba": "",
        "extra_recorders": "",
        "target_text": row.target_text,
        "user_text": row.user_text,
        "notes": "",
    }
    for part in row.variant.split("-"):
        for key, value in VARIABLE_FIELDS.get(part, {}).items():
            fields[key] = (
                value if key != "notes" else "；".join(filter(None, [fields["notes"], value]))
            )
    return fields


CSS = """
@page { size: A4; margin: 12mm 10mm; }
* { box-sizing: border-box; }
body { font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif; font-size: 10.5pt;
       color: #111; background: #fff; margin: 0 auto; max-width: 190mm; line-height: 1.45; }
h1 { font-size: 18pt; margin: 0 0 4mm; }
h2 { font-size: 13pt; margin: 6mm 0 2mm; padding: 1.5mm 2mm; background: #eee;
     border-left: 3px solid #111; }
h2 .meta { font-weight: normal; font-size: 9.5pt; color: #444; margin-left: 2mm; }
h3 { font-size: 11pt; margin: 4mm 0 1.5mm; }
.day { font-size: 15pt; margin: 0 0 2mm; padding-bottom: 1mm; border-bottom: 2px solid #111; }
.page { break-before: page; }
table { width: 100%; border-collapse: collapse; margin: 1mm 0 2mm; }
th, td { border: 1px solid #999; padding: 1mm 1.5mm; vertical-align: top; }
th { background: #f4f4f4; font-weight: 600; text-align: left; }
tr { break-inside: avoid; }
td.box, th.box { width: 7mm; text-align: center; }
td.no { width: 8mm; text-align: right; color: #555; }
td.file { font-family: "PingFang SC", monospace; font-size: 9.5pt; width: 70mm;
          word-break: break-all; }
td.take { width: 18mm; }
.square { display: inline-block; width: 3.6mm; height: 3.6mm; border: 1.2px solid #111; }
ul.setup { margin: 1mm 0 2mm; padding-left: 0; list-style: none; }
ul.setup li { margin: 0.6mm 0; }
ul.setup li::before { content: ""; display: inline-block; width: 3.2mm; height: 3.2mm;
                      border: 1.2px solid #111; margin-right: 2mm; vertical-align: -0.4mm; }
.note { font-size: 9.5pt; color: #333; }
.opt { color: #666; font-weight: normal; }
blockquote { margin: 1mm 0 2.5mm; padding: 1.5mm 3mm; border-left: 3px solid #999;
             background: #fafafa; }
.script td { font-size: 10pt; }
"""


def render(sections: list[Section]) -> str:
    out: list[str] = []
    esc = html.escape
    total = sum(len(s.rows) for s in sections)
    required = sum(len(s.rows) for s in sections if not s.optional)
    out.append(
        f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>录音清单</title>"
        f"<style>{CSS}</style></head><body>"
    )
    out.append("<h1>双领夹麦录音清单</h1>")
    out.append(
        "<p class='note'>A = 对方（左声道），B = 我（右声道）。"
        f"共 {total} 条，其中必录和建议 {required} 条。"
        "文件名默认是“第1遍”；重录时把最后改成“第2遍”，并在“遍数”一栏写下采用哪一遍。"
        "每条开头口报场记，例如“安静包间，同时说，第 2 段，第 1 遍”，再拍一次手。</p>"
    )
    out.append("<h3>出发前</h3><ul class='setup'>")
    for item in BEFORE_LEAVING:
        out.append(f"<li>{esc(item)}</li>")
    out.append("</ul>")

    current_day = ""
    no = 0
    for section in sections:
        if section.day != current_day:
            page = " class='page'" if current_day else ""
            current_day = section.day
            out.append(f"<div{page}><div class='day'>{esc(current_day)}</div></div>")
        tag = "<span class='opt'>（可选）</span>" if section.optional else ""
        out.append(
            f"<h2>{esc(section.title)}{tag}<span class='meta'>约 {section.minutes} 分钟 · "
            f"{len(section.rows)} 条 · 文件名开头：{esc(section.location)}</span></h2>"
        )
        out.append(
            "<ul class='setup'>" + "".join(f"<li>{esc(s)}</li>" for s in section.setup) + "</ul>"
        )
        out.append(
            "<table><thead><tr><th class='box'>✓</th><th>#</th><th>文件名</th><th>要做什么</th>"
            "<th>遍数</th></tr></thead><tbody>"
        )
        for row in section.rows:
            no += 1
            out.append(
                f"<tr><td class='box'><span class='square'></span></td><td class='no'>{no}</td>"
                f"<td class='file'>{esc(filename(section.location, row))}</td>"
                f"<td>{esc(row.hint)}</td><td class='take'></td></tr>"
            )
        out.append("</tbody></table>")

    out.append("<div class='page'><div class='day'>附录：稿子</div></div>")
    out.append("<h3>声纹稿</h3>")
    out.append(f"<p><b>A：</b></p><blockquote>{esc(ENROLL_A)}</blockquote>")
    out.append(f"<p><b>B：</b></p><blockquote>{esc(ENROLL_B)}</blockquote>")
    out.append("<h3>对方单说（A 读，B 不出声）</h3>")
    for i, text in enumerate(A_ONLY, 1):
        out.append(f"<p><b>{i:02d}</b></p><blockquote>{esc(text)}</blockquote>")
    out.append("<h3>我单说（B 读，A 不出声）</h3>")
    for i, text in enumerate(B_ONLY, 1):
        out.append(f"<p><b>{i:02d}</b></p><blockquote>{esc(text)}</blockquote>")
    out.append("<h3>交替说（上一句读完立刻接下一句）</h3>")
    for i, turns in enumerate(ALTERNATING, 1):
        out.append(f"<p><b>{i:02d}</b></p><table class='script'><tbody>")
        out.extend(f"<tr><td style='width:10mm'>{s}</td><td>{esc(t)}</td></tr>" for s, t in turns)
        out.append("</tbody></table>")
    out.append("<h3>同时说（数到三同时开始，各读各的，不要停）</h3>")
    out.append(
        "<table class='script'><thead><tr><th style='width:10mm'>#</th>"
        "<th>A 读</th><th>B 同时读</th>"
        "</tr></thead><tbody>"
    )
    for i, (a, b) in enumerate(OVERLAP, 1):
        out.append(f"<tr><td>{i:02d}</td><td>{esc(a)}</td><td>{esc(b)}</td></tr>")
    out.append("</tbody></table>")
    out.append("<h3>附和稿（A 读，B 在句间插“嗯”“对”“是吗”“真的啊”）</h3>")
    out.append(f"<blockquote>{esc(BACKCHANNEL)}</blockquote>")
    out.append("<h3>打断稿</h3><table class='script'><tbody>")
    out.extend(f"<tr><td style='width:10mm'>{s}</td><td>{esc(t)}</td></tr>" for s, t in INTERRUPT)
    out.append("</tbody></table>")
    out.append("<h3>数字稿（A 读；全部为虚构信息）</h3>")
    out.append(f"<blockquote>{esc(NUMBERS)}</blockquote>")
    out.append(
        "<h3>话题卡（自由聊天和长独白用；不要说真实的电话、证件号、住址）</h3>"
        "<table class='script'><tbody>"
    )
    for i, topic in enumerate(TOPICS, 1):
        out.append(f"<tr><td style='width:10mm'>{i}</td><td>{esc(topic)}</td></tr>")
    out.append("</tbody></table></body></html>")
    return "\n".join(out)


def render_markdown(sections: list[Section], scripts_link: str) -> str:
    total = sum(len(s.rows) for s in sections)
    required = sum(len(s.rows) for s in sections if not s.optional)
    out = [
        "# 双领夹麦录音清单",
        "",
        f"A = 对方（左声道），B = 我（右声道）。共 {total} 条，其中必录和建议 {required} 条。"
        "录完一条就勾掉一条。文件名可以长按复制，粘贴到语音备忘录里改名。",
        "",
        "重录时把文件名最后改成“第2遍”，并在该行末尾补写“采用第2遍”。"
        "每条开头口报场记，例如“安静包间，同时说，第 2 段，第 1 遍”，再拍一次手。",
        "",
        f"稿子见 {scripts_link}。",
        "",
        f"> {HEADPHONE_CHECK}",
        "",
        "## 出发前",
        "",
        *[f"- [ ] {item}" for item in BEFORE_LEAVING],
    ]
    current_day = ""
    no = 0
    for section in sections:
        if section.day != current_day:
            current_day = section.day
            out += ["", f"## {current_day}"]
        tag = "（可选）" if section.optional else ""
        out += [
            "",
            f"### {section.title}{tag}",
            "",
            f"约 {section.minutes} 分钟 · {len(section.rows)} 条 · 文件名开头：{section.location}",
            "",
            *[f"- [ ] {item}" for item in section.setup],
            "",
        ]
        for row in section.rows:
            no += 1
            out.append(f"- [ ] {no}. `{filename(section.location, row)}` {row.hint}")
    return "\n".join(out) + "\n"


def render_scripts_markdown() -> str:
    out = ["# 双领夹麦录音稿", "", "A = 对方，B = 我。用平常聊天的语速和音量，读错了不用重来。", ""]
    out += ["## 声纹稿", "", "**A：**", "", f"> {ENROLL_A}", "", "**B：**", "", f"> {ENROLL_B}", ""]
    out += ["## 对方单说（A 读，B 不出声）", ""]
    for i, text in enumerate(A_ONLY, 1):
        out += [f"**{i:02d}**", "", f"> {text}", ""]
    out += ["## 我单说（B 读，A 不出声）", ""]
    for i, text in enumerate(B_ONLY, 1):
        out += [f"**{i:02d}**", "", f"> {text}", ""]
    out += ["## 交替说（上一句读完立刻接下一句）", ""]
    for i, turns in enumerate(ALTERNATING, 1):
        out += [f"**{i:02d}**", ""]
        out += [f"- **{speaker}**：{text}" for speaker, text in turns]
        out.append("")
    out += ["## 同时说（数到三同时开始，各读各的，不要停）", ""]
    for i, (a, b) in enumerate(OVERLAP, 1):
        out += [f"**{i:02d}**", "", f"- **A**：{a}", f"- **B**：{b}", ""]
    out += ["## 附和稿（A 读，B 在句间插“嗯”“对”“是吗”“真的啊”）", "", f"> {BACKCHANNEL}", ""]
    out += ["## 打断稿", ""]
    out += [f"- **{speaker}**：{text}" for speaker, text in INTERRUPT]
    out += ["", "## 数字稿（A 读；全部为虚构信息）", "", f"> {NUMBERS}", ""]
    out += ["## 话题卡（自由聊天和长独白用；不要说真实的电话、证件号、住址）", ""]
    out += [f"{i}. {topic}" for i, topic in enumerate(TOPICS, 1)]
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("docs/experiments"))
    parser.add_argument(
        "--scripts-link",
        default="[录音稿](./lavalier_recording_scripts.md)",
        help="清单中指向录音稿的链接，例如 Obsidian 的 [[笔记名]]",
    )
    args = parser.parse_args()
    sections = build_sections()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "lavalier_recording_checklist.html").write_text(
        render(sections), encoding="utf-8"
    )
    (args.out_dir / "lavalier_recording_checklist.md").write_text(
        render_markdown(sections, args.scripts_link), encoding="utf-8"
    )
    (args.out_dir / "lavalier_recording_scripts.md").write_text(
        render_scripts_markdown(), encoding="utf-8"
    )
    rows = [manifest_row(s, r) for s in sections for r in s.rows]
    with (args.out_dir / "lavalier_manifest_template.tsv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    names = [r["file"] for r in rows]
    duplicates = {n for n in names if names.count(n) > 1}
    print(f"{len(rows)} rows; duplicates: {sorted(duplicates) or 'none'}")


if __name__ == "__main__":
    main()
