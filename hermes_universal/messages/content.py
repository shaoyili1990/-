"""
多模态消息内容系统
支持: text / image / file / audio
自动类型检测和编码处理
"""

import base64
import mimetypes
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union


@dataclass
class ContentPart:
    """统一内容片段基类"""
    type: str = "text"

    def to_dict(self) -> Dict:
        return {"type": self.type}


@dataclass
class TextContent(ContentPart):
    """文本内容"""
    type: str = "text"
    text: str = ""

    def to_dict(self) -> Dict:
        return {"type": "text", "text": self.text}


@dataclass
class ImageContent(ContentPart):
    """图像内容 - base64编码"""
    type: str = "image"
    data: str = ""  # base64编码数据
    mime_type: str = "image/jpeg"
    url: str = ""  # 可选URL
    detail: str = "auto"  # low / high / auto

    def to_dict(self) -> Dict:
        if self.url and not self.data:
            return {"type": "image", "image_url": {"url": self.url, "detail": self.detail}}
        data_uri = f"data:{self.mime_type};base64,{self.data}"
        return {"type": "image", "image_url": {"url": data_uri, "detail": self.detail}}


@dataclass
class FileContent(ContentPart):
    """文件内容 - base64编码"""
    type: str = "file"
    data: str = ""
    mime_type: str = "application/octet-stream"
    filename: str = "file"

    def to_dict(self) -> Dict:
        return {
            "type": "file",
            "data": self.data,
            "mime_type": self.mime_type,
            "filename": self.filename,
        }


@dataclass
class Message:
    """统一消息格式"""
    role: str = "user"  # system / user / assistant / tool
    content: List[ContentPart] = field(default_factory=list)

    def add_text(self, text: str) -> "Message":
        self.content.append(TextContent(text=text))
        return self

    def add_image(self, data: str, mime_type: str = "image/jpeg",
                  url: str = "", detail: str = "auto") -> "Message":
        self.content.append(ImageContent(data=data, mime_type=mime_type,
                                         url=url, detail=detail))
        return self

    def add_file(self, data: str, mime_type: str, filename: str) -> "Message":
        self.content.append(FileContent(data=data, mime_type=mime_type,
                                        filename=filename))
        return self

    def to_list(self) -> List[Dict]:
        """转换为API消息格式"""
        if len(self.content) == 1 and self.content[0].type == "text":
            return [{"role": self.role, "content": self.content[0].text}]

        parts = [c.to_dict() for c in self.content]
        return [{"role": self.role, "content": parts}]

    @classmethod
    def from_text(cls, role: str, text: str) -> "Message":
        return cls(role=role, content=[TextContent(text=text)])

    @classmethod
    def from_file(cls, filepath: str, role: str = "user") -> "Message":
        """从文件创建消息，自动检测类型"""
        if not os.path.exists(filepath):
            return cls.from_text(role, f"[文件未找到: {filepath}]")

        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = "application/octet-stream"

        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")

        msg = cls(role=role)

        if mime_type.startswith("image/"):
            msg.add_image(data, mime_type)
        else:
            msg.add_file(data, mime_type, os.path.basename(filepath))

        return msg


def load_image(image_input: Union[str, bytes, None]) -> Optional[ImageContent]:
    """加载图像 - 支持路径/URL/bytes"""
    if image_input is None:
        return None
    if isinstance(image_input, bytes):
        mime_type = "image/png"
        data = base64.b64encode(image_input).decode("ascii")
        return ImageContent(data=data, mime_type=mime_type)
    if os.path.exists(image_input):
        mime_type, _ = mimetypes.guess_type(image_input)
        if not mime_type:
            mime_type = "image/png"
        with open(image_input, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return ImageContent(data=data, mime_type=mime_type)
    # 假设是URL
    return ImageContent(url=image_input, mime_type="image/jpeg")


def auto_encode_text(text: str, target_encoding: str = "utf-8") -> str:
    """自适应编码 - 内部统一UTF8"""
    if target_encoding.lower() == "utf-8" or target_encoding.lower() == "utf8":
        return text
    try:
        return text.encode("utf-8").decode(target_encoding)
    except:
        return text


def auto_decode_text(text: bytes, source_encoding: str = None) -> str:
    """自动解码字节到UTF8"""
    if source_encoding:
        try:
            return text.decode(source_encoding)
        except:
            pass
    # 尝试常见编码
    for enc in ["utf-8", "gbk", "gb2312", "big5"]:
        try:
            return text.decode(enc)
        except:
            continue
    return text.decode("utf-8", errors="replace")
