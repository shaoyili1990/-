"""
AutoDL 临时服务器 MCP 工具配置
存为结构化 JSON + Python 工具类，供后续任何模块调用检验连接
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

# ===== MCP 资源定义：AutoDL 实例连接 =====
AUTODL_CONFIG = {
    "instances": [
        {
            "name": "autodl-instance-main",
            "description": "AutoDL 无卡模式主实例",
            "local_url": "http://127.0.0.1:6006",
            "public_url": "https://u892543-00c5-8790f987.westd.seetacloud.com:8443",
            "ssh": {
                "host": "connect.westd.seetacloud.com",
                "port": 20168,
                "user": "root",
                "password": "iS3Osyuq7nv8",
            },
            "type": "gradio",
            "warning": "严禁使用WebUI等算法生成违禁图片，一经发现立即封号！",
        },
        {
            "name": "autodl-instance-extra",
            "description": "AutoDL 无卡模式附加实例",
            "local_url": "http://127.0.0.1:6008",
            "public_url": "https://uu892543-00c5-8790f987.westd.seetacloud.com:8443",
            "ssh": {
                "host": "connect.westd.seetacloud.com",
                "port": 20168,
                "user": "root",
                "password": "iS3Osyuq7nv8",
            },
            "type": "gradio",
            "warning": "严禁使用WebUI等算法生成违禁图片，一经发现立即封号！",
        },
    ],
    "meta": {
        "version": "1.0",
        "updated": "2025-07-19",
        "description": "AutoDL 临时服务器无卡模式连接配置,用于模型推理和API服务",
    },
}


# ===== MCP 工具实现 =====

def get_autodl_config() -> Dict:
    """获取 AutoDL 实例配置列表"""
    return AUTODL_CONFIG


def test_ssh_connection(instance_name: str = "autodl-instance-main") -> Dict:
    """测试 SSH 连接是否可用"""
    instances = {i["name"]: i for i in AUTODL_CONFIG["instances"]}
    inst = instances.get(instance_name)
    if not inst:
        return {"ok": False, "message": f"实例 {instance_name} 不存在"}

    ssh = inst["ssh"]
    try:
        result = subprocess.run(
            [
                "sshpass", "-p", ssh["password"],
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=10",
                "-p", str(ssh["port"]),
                f"{ssh['user']}@{ssh['host']}",
                "echo connected && hostname",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return {"ok": True, "hostname": result.stdout.strip(), "instance": instance_name}
        else:
            return {"ok": False, "error": result.stderr[:200], "instance": instance_name}
    except FileNotFoundError:
        return {"ok": False, "error": "sshpass not installed", "instance": instance_name}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "instance": instance_name}


def check_urls(instance_name: str = "autodl-instance-main") -> Dict:
    """检查实例的 public_url 是否可访问"""
    instances = {i["name"]: i for i in AUTODL_CONFIG["instances"]}
    inst = instances.get(instance_name)
    if not inst:
        return {"ok": False, "message": f"实例 {instance_name} 不存在"}

    import urllib.request
    urls = {"public": inst["public_url"], "local": inst["local_url"]}
    results = {}
    for name, url in urls.items():
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                results[name] = {"ok": True, "status": resp.status}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)[:100]}
    return {"instance": instance_name, "checks": results}


def format_mcp_summary() -> str:
    """格式化为可读的 MCP 摘要"""
    lines = ["## 📡 AutoDL 实例 MCP 配置", ""]
    for inst in AUTODL_CONFIG["instances"]:
        lines.append(f"### {inst['name']}")
        lines.append(f"- 描述: {inst['description']}")
        lines.append(f"- 本地: `{inst['local_url']}`")
        lines.append(f"- 公网: `{inst['public_url']}`")
        lines.append(f"- SSH: `ssh -p {inst['ssh']['port']} {inst['ssh']['user']}@{inst['ssh']['host']}`")
        lines.append(f"- 密码: `{inst['ssh']['password']}`")
        lines.append(f"")
    lines.append("> ⚠️ " + AUTODL_CONFIG["instances"][0]["warning"])
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_mcp_summary())
    print("\n--- SSH Test ---")
    print(json.dumps(test_ssh_connection(), ensure_ascii=False, indent=2))
