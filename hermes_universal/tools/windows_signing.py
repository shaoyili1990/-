"""
Windows 数字签名配置 — MCP 工具模块

本模块提供 Hermes Agent Windows 发布的数字签名配置，
记录当前最优方案（SignPath Foundation 免费开源签名）的完整信息。

使用方式:
    from hermes_universal.tools import windows_signing
    info = windows_signing.get_config()
"""

import os
from typing import Optional

# ─── 签名方案配置 ───────────────────────────────────────────────

# 当前推荐方案（2025.07 — 测试期/开源项目）
RECOMMENDED_SCHEME = "signpath_foundation"

SCHEMES = {
    # P0: 优先选免费的
    "signpath_foundation": {
        "name": "SignPath Foundation",
        "url": "https://signpath.org",
        "cost": "free",
        "trust_level": "windows_trusted",
        "publisher_name": "SignPath Foundation",
        "requirements": [
            "OSI-approved 开源许可证（MIT）",
            "公开 GitHub 仓库",
            "免费下载的发布版（GitHub Releases）",
            "README 添加代码签名策略声明",
            "CI 构建（GitHub Actions）",
        ],
        "process": [
            "在项目 README 添加代码签名策略章节",
            "访问 signpath.org → Apply 填写申请",
            "等待审批（通常 1-2 周）",
            "配置 GitHub Actions 签名工作流",
            "提交流程自动触发签名",
        ],
        "notes": "发布者名称显示为 SignPath Foundation，不是项目名。免个人身份验证。",
        "suitable_for": "开源测试版/正式版",
    },
    "ossign": {
        "name": "OSSign",
        "url": "https://ossign.org",
        "cost": "free",
        "trust_level": "windows_trusted",
        "publisher_name": "OSSign",
        "requirements": [
            "开源项目",
            "非政治/争议性项目",
        ],
        "process": [
            "访问 ossign.org → Apply",
            "填写项目信息",
            "等待审批",
        ],
        "notes": "比 SignPath 信息少，作为备选。",
        "suitable_for": "开源测试版/正式版",
    },
    # P1: 免费方案走不通时
    "certum": {
        "name": "Certum Code Signing",
        "url": "https://www.certum.pl",
        "cost": "~$169/年（约¥1200）",
        "trust_level": "windows_trusted",
        "publisher_name": "你的名字/公司",
        "requirements": [
            "个人或公司身份验证",
            "可委托代购（支持支付宝/微信）",
        ],
        "process": [
            "通过代理/代购购买 Certum 证书",
            "提供身份验证材料",
            "接收 .pfx 文件",
            "用 signtool 签名",
        ],
        "notes": "最便宜的付费方案。可通过国内代购用支付宝/微信支付。",
        "suitable_for": "不适合 SignPath/OSSign 时的付费备选",
    },
    "azure_trusted_signing": {
        "name": "Azure Trusted Signing",
        "url": "https://azure.microsoft.com/en-us/products/trusted-signing",
        "cost": "~$10/月（约¥72，可免费信用额度抵扣）",
        "trust_level": "windows_trusted",
        "publisher_name": "你的公司名",
        "requirements": [
            "Azure 账号（需国际信用卡）",
            "公司/个人身份验证（Microsoft Entra）",
            "主要支持美国/加拿大/欧盟",
        ],
        "process": [
            "注册 Azure 账号",
            "创建 Trusted Signing 账户",
            "Identity Validation",
            "创建 Certificate Profile",
            "集成 CI 环境变量签名",
        ],
        "notes": "2025年12月31日后可能终止服务。需国际信用卡。中国区域支持有限。",
        "suitable_for": "已使用 Azure 的国际团队",
    },
    "self_signed": {
        "name": "自签名证书",
        "cost": "free",
        "trust_level": "untrusted",
        "publisher_name": "未验证",
        "notes": "Windows SmartScreen 会显示警告。仅开发测试用。",
        "suitable_for": "开发测试/等待审批期间过渡",
    },
}

# ─── 项目配置 ───────────────────────────────────────────────────

PROJECT = {
    "name": "Hermes Agent",
    "repo_url": "https://github.com/shaoyili1990/-",
    "license": "MIT",
    "primary_branch": "main",
    "ci": "GitHub Actions",
    "current_version": "0.1.0",
    "current_scheme": RECOMMENDED_SCHEME,
    "status": "pending_approval",  # pending_approval | approved | signed
}

# ─── AutoDL 服务器配置 ──────────────────────────────────────────

AUTODL = {
    "description": "Hermes Agent 临时 AutoDL 服务器",
    "mode": "无卡模式",
    "instances": [
        {
            "name": "主实例",
            "local_url": "http://127.0.0.1:6006",
            "public_url": "https://u892543-00c5-8790f987.westd.seetacloud.com:8443",
        },
        {
            "name": "附加实例",
            "local_url": "http://127.0.0.1:6008",
            "public_url": "https://uu892543-00c5-8790f987.westd.seetacloud.com:8443",
        },
    ],
    "ssh": {
        "host": "connect.westd.seetacloud.com",
        "port": 20168,
        "user": "root",
        "password": "iS3Osyuq7nv8",
        "command": "ssh -p 20168 root@connect.westd.seetacloud.com",
    },
    "warning": "严禁使用WebUI等算法生成违禁图片，一经发现立即封号！",
    "notes": "仅用于开发和测试。生产环境请使用自有服务器。",
}


# ─── API ────────────────────────────────────────────────────────

def get_config(scheme: Optional[str] = None) -> dict:
    """获取签名方案配置"""
    if scheme and scheme in SCHEMES:
        return {
            "project": PROJECT,
            "scheme": SCHEMES[scheme],
            "scheme_key": scheme,
        }
    return {
        "project": PROJECT,
        "available_schemes": list(SCHEMES.keys()),
        "recommended": RECOMMENDED_SCHEME,
        "recommended_detail": SCHEMES[RECOMMENDED_SCHEME],
    }


def get_autodl_config() -> dict:
    """获取 AutoDL 服务器配置"""
    return AUTODL


def format_config_markdown(include_signing: bool = True, include_autodl: bool = True) -> str:
    """格式化为 Markdown"""
    parts = []

    if include_signing:
        parts.append("## 📜 Windows 签名配置")
        parts.append("")
        parts.append(f"**当前方案**: {SCHEMES[RECOMMENDED_SCHEME]['name']} ({SCHEMES[RECOMMENDED_SCHEME]['cost']})")
        parts.append("")
        parts.append("| 优先级 | 方案 | 费用 | 信任 | 适合 |")
        parts.append("|:------:|:-----|:----:|:----:|:----:|")
        for i, key in enumerate(["signpath_foundation", "ossign", "certum", "azure_trusted_signing", "self_signed"]):
            s = SCHEMES[key]
            p = "P0" if i == 0 else f"P{i}"
            parts.append(f"| {p} | {s['name']} | {s['cost']} | {s['trust_level']} | {s['suitable_for']} |")
        parts.append("")

    if include_autodl:
        parts.append("## 📡 AutoDL 服务器")
        parts.append("")
        for inst in AUTODL["instances"]:
            parts.append(f"- **{inst['name']}**: {inst['local_url']} → {inst['public_url']}")
        parts.append("")
        parts.append(f"- **SSH**: `{AUTODL['ssh']['command']}`")
        parts.append(f"- **密码**: `{AUTODL['ssh']['password']}`")
        parts.append(f"- **⚠️**: {AUTODL['warning']}")

    return "\n".join(parts)


def test_ssh_connection() -> dict:
    """模拟 SSH 连接测试（需要在有网络和 ssh 命令的环境中执行）"""
    return {
        "command": AUTODL["ssh"]["command"],
        "expected": "可连接",
        "note": "实际连接请在终端执行: " + AUTODL["ssh"]["command"],
    }
