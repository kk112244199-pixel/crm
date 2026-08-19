"""
PII NER — 规则 + 中文扩展（不依赖 Presidio/torch；可作降级路径）

识别：手机、身份证（18 位校验）、邮箱、带称谓的中文姓名。
"""
from __future__ import annotations
import re
from dataclasses import dataclass

_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID18 = re.compile(
    r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
)

# 常见单字姓（覆盖 golden / 种子客户）
_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐费薛雷贺"
    "倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵"
    "汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜蓝闵季贾江童"
    "颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯卢莫房丁邓杭洪包左石"
    "崔吉程嵇邢陆荣翁荀于惠甄储靳段富巫乌焦车侯谷梁刘景詹束龙叶司韶黎"
    "白蒲邰鄂索咸赖卓蔺屠蒙池乔阴翟谭贡劳逄姬申冉宰郦雍桑桂濮牛寿通边"
    "扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾居衡"
    "耿满弘匡国文寇广禄阙欧聂晁勾敖融冷訾辛阚简饶曾毋沙养鞠丰巢关蒯相"
    "查荆红游竺权逯盖益桓商牟佘佴伯赏墨哈谯笪年爱阳佟"
)

_NAME_AFTER_TITLE = re.compile(
    rf"(?:先生|女士|小姐|经理|总监|主任|工程师|老板|联系人|对接人)[：:\s]*"
    rf"([{_SURNAMES}][一-龥]{{1,2}})"
)
_NAME_BEFORE_TITLE = re.compile(
    rf"([{_SURNAMES}][一-龥]{{1,2}})\s*(?:先生|女士|小姐|经理|总监|主任|总|工)(?![一-龥])"
)

_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID_CHECK = "10X98765432"


@dataclass
class PIISpan:
    start: int
    end: int
    label: str
    value: str


def _valid_cn_id18(s: str) -> bool:
    if len(s) != 18:
        return False
    total = 0
    try:
        for i, w in enumerate(_ID_WEIGHTS):
            total += int(s[i]) * w
    except ValueError:
        return False
    return _ID_CHECK[total % 11] == s[17].upper()


def find_pii(text: str) -> list[PIISpan]:
    spans: list[PIISpan] = []
    for m in _PHONE.finditer(text):
        spans.append(PIISpan(m.start(), m.end(), "phone_number", m.group()))
    for m in _EMAIL.finditer(text):
        spans.append(PIISpan(m.start(), m.end(), "email", m.group()))
    for m in _ID18.finditer(text):
        if _valid_cn_id18(m.group()):
            spans.append(PIISpan(m.start(), m.end(), "id_card", m.group()))
    for m in _NAME_AFTER_TITLE.finditer(text):
        g = m.group(1)
        spans.append(PIISpan(m.start(1), m.end(1), "person_name", g))
    for m in _NAME_BEFORE_TITLE.finditer(text):
        g = m.group(1)
        spans.append(PIISpan(m.start(1), m.end(1), "person_name", g))
    # merge overlaps, prefer longer
    spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
    merged: list[PIISpan] = []
    for s in spans:
        if merged and s.start < merged[-1].end:
            continue
        merged.append(s)
    return merged


def redact_pii(text: str) -> str:
    spans = find_pii(text)
    if not spans:
        return text
    out = []
    last = 0
    for s in spans:
        out.append(text[last:s.start])
        out.append(f"[{s.label.upper()}_REDACTED]")
        last = s.end
    out.append(text[last:])
    return "".join(out)


def pii_labels_present(text: str) -> list[str]:
    return sorted({s.label for s in find_pii(text)})
