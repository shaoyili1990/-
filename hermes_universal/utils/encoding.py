"""
编码自适应工具
原则: 内部统一UTF8, 外部输入自动转UTF8, 输出自动转目标编码
"""

import os
import sys

AUTO_ENCODING = "utf-8"


def detect_encoding(data: bytes = None) -> str:
    """检测编码"""
    if data:
        import chardet
        try:
            result = chardet.detect(data)
            return result["encoding"] or "utf-8"
        except ImportError:
            pass
        for enc in ["utf-8", "gbk", "gb2312", "big5", "shift-jis"]:
            try:
                data.decode(enc)
                return enc
            except:
                continue
    # 环境检测
    for var in ["LC_ALL", "LC_CTYPE", "LANG"]:
        val = os.environ.get(var, "")
        if "GBK" in val.upper() or "936" in val:
            return "gbk"
        if "BIG5" in val.upper() or "950" in val:
            return "big5"
    return "utf-8"


def ensure_unicode(text: str, source_enc: str = None) -> str:
    """确保文本是Unicode(UTF8)"""
    if isinstance(text, str):
        return text
    if isinstance(text, bytes):
        if source_enc:
            try:
                return text.decode(source_enc)
            except:
                pass
        for enc in ["utf-8", "gbk", "gb2312", "big5"]:
            try:
                return text.decode(enc)
            except:
                continue
        return text.decode("utf-8", errors="replace")
    return str(text)


def encode_output(text: str, target_enc: str = None) -> str:
    """输出时编码转换"""
    if not target_enc or target_enc.lower() in ("utf-8", "utf8"):
        return text
    try:
        return text.encode("utf-8").decode(target_enc)
    except:
        return text
