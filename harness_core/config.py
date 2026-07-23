"""
配置系统 - 三层合并: YAML < 环境变量 < CLI参数
支持任意AI厂商API Key配置和混搭模式
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# 默认配置
DEFAULT_CONFIG = {
    "monkey": {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "horse": {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0.7,
        "max_tokens": 8192,
    },
    "purchaser": {
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0.5,
        "max_tokens": 2048,
    },
    "keeper": {
        "db_path": "",
        "auto_migrate": True,
    },
    "scribe": {
        "db_path": "",
        "auto_init": True,
    },
    "system": {
        "subchains_dir": "",
        "fingerprints_dir": "",
        "store_dir": "",
        "encoding": "utf-8",
        "auto_encoding": True,
    },
    "providers": {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini", "o1"],
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-latest", "claude-3-opus-latest"],
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash"],
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "models": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "models": ["llama3", "qwen2.5", "mistral", "deepseek-r1", "phi-4"],
            "local": True,
            "note": "输入本地模型名称，需先 ollama pull",
        },
        "vllm": {
            "base_url": "http://localhost:8000/v1",
            "models": [],
            "local": True,
            "note": "输入已部署的模型名称，需先启动 vllm serve",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "models": ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "deepseek/deepseek-chat", "google/gemini-2.0-flash"],
        },
    }
}


class Config:
    """三层配置系统"""

    def __init__(self, config_path: Optional[str] = None, **overrides):
        self._data = self._merge_configs(config_path, overrides)

    def _merge_configs(self, config_path: Optional[str], overrides: Dict) -> Dict:
        """合并默认配置 + YAML文件 + 环境变量 + CLI参数"""
        config = self._deep_copy(DEFAULT_CONFIG)

        # 1. 加载YAML文件
        if config_path and os.path.exists(config_path):
            yaml_config = self._load_yaml(config_path)
            self._deep_merge(config, yaml_config)

        # 2. 环境变量覆盖
        self._apply_env(config)

        # 3. CLI参数覆盖
        self._deep_merge(config, overrides)

        # 4. 自动填充路径
        self._resolve_paths(config)

        # 5. 自动检测编码
        if config["system"]["auto_encoding"]:
            config["system"]["encoding"] = self._detect_encoding()

        return config

    def _load_yaml(self, path: str) -> Dict:
        """加载YAML配置，若pyyaml不可用则fallback到JSON"""
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            try:
                import json
                with open(path.replace(".yaml", ".json"), "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}

    def _apply_env(self, config: Dict):
        """环境变量覆盖"""
        env_map = {
            "MONKEY_PROVIDER": ("monkey", "provider"),
            "MONKEY_MODEL": ("monkey", "model"),
            "MONKEY_KEY": ("monkey", "api_key"),
            "HERMES_MONKEY_BASE_URL": ("monkey", "base_url"),
            "HORSE_PROVIDER": ("horse", "provider"),
            "HORSE_MODEL": ("horse", "model"),
            "MONKEY_HORSE_KEY": ("horse", "api_key"),
            "HERMES_HORSE_BASE_URL": ("horse", "base_url"),
            "HERMES_PURCHASER_PROVIDER": ("purchaser", "provider"),
            "HERMES_PURCHASER_MODEL": ("purchaser", "model"),
            "HERMES_PURCHASER_KEY": ("purchaser", "api_key"),
            "HERMES_PURCHASER_BASE_URL": ("purchaser", "base_url"),
            "HERMES_DB_PATH": ("keeper", "db_path"),
            "MONKEY_STORE_DIR": ("system", "store_dir"),
            "MONKEY_ENCODING": ("system", "encoding"),
        }
        # 通用API Key环境变量
        provider_keys = {
            "OPENAI_API_KEY": ("providers", "openai", "api_key"),
            "ANTHROPIC_API_KEY": ("providers", "anthropic", "api_key"),
            "DEEPSEEK_API_KEY": ("providers", "deepseek", "api_key"),
            "GOOGLE_API_KEY": ("providers", "google", "api_key"),
        }

        for env_key, path in {**env_map, **provider_keys}.items():
            val = os.environ.get(env_key)
            if val:
                self._set_nested(config, path, val)

    def _resolve_paths(self, config: Dict):
        """自动解析项目路径（支持 PyInstaller 打包环境）"""
        # PyInstaller onefile: 资源在 sys._MEIPASS
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent.parent  # monkey-harness-agent/

        # 用户数据目录（可写，持久化）
        user_data_dir = self._get_user_data_dir()

        if not config["system"]["subchains_dir"]:
            config["system"]["subchains_dir"] = str(base / "subchains")
        if not config["system"]["fingerprints_dir"]:
            config["system"]["fingerprints_dir"] = str(base / "fingerprints")
        if not config["system"]["store_dir"]:
            store_dir = user_data_dir / "store"
            store_dir.mkdir(parents=True, exist_ok=True)
            config["system"]["store_dir"] = str(store_dir)
            # 首次运行：从打包目录复制初始 DB 到用户数据目录
            self._ensure_db_init(base, user_data_dir)
        if not config["keeper"]["db_path"]:
            config["keeper"]["db_path"] = str(user_data_dir / "store" / "rnd_engine.db")
        if not config["scribe"]["db_path"]:
            config["scribe"]["db_path"] = str(user_data_dir / "store" / "harness.db")

    def _get_user_data_dir(self) -> Path:
        """获取用户数据目录（跨平台）"""
        if os.name == 'nt':  # Windows
            base = Path(os.environ.get('APPDATA', ''))
        elif sys.platform == 'darwin':  # macOS
            base = Path.home() / 'Library' / 'Application Support'
        else:  # Linux
            base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
        return base / 'HermesAgent'

    def _ensure_db_init(self, base: Path, user_data_dir: Path):
        """首次运行时将打包的 DB 复制到用户数据目录"""
        store_target = user_data_dir / "store"
        for db_name in ['rnd_engine.db', 'harness.db']:
            src = base / "store" / db_name
            dst = store_target / db_name
            if src.exists() and not dst.exists():
                try:
                    import shutil
                    shutil.copy2(str(src), str(dst))
                except Exception:
                    pass

    def _detect_encoding(self) -> str:
        """自动检测终端编码"""
        enc = os.environ.get("LC_ALL", "") or os.environ.get("LC_CTYPE", "") or os.environ.get("LANG", "")
        if "GBK" in enc.upper() or "GB2312" in enc.upper() or "936" in enc:
            return "gbk"
        return "utf-8"

    def get(self, *keys, default=None):
        """安全获取嵌套配置值: config.get('monkey','provider')"""
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def _get_key_from_db(self, role: str) -> str:
        """从状态机多维表格(api_credentials)读取API Key"""
        db_path = self._data.get("keeper", {}).get("db_path", "")
        if not db_path:
            return ""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            # Step 1: get cred_id from env_config via role_key_{role}
            cur.execute("SELECT value FROM env_config WHERE key = ?", (f"role_key_{role}",))
            row = cur.fetchone()
            if not row:
                return ""
            import json
            env_val = json.loads(row[0])
            cred_id = env_val.get("cred_id")
            if not cred_id:
                return ""
            # Step 2: get key_value from api_credentials
            cur.execute("SELECT key_value FROM api_credentials WHERE id = ?", (cred_id,))
            row = cur.fetchone()
            if not row:
                return ""
            return row[0]
        except Exception:
            return ""
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_provider_config(self, role: str) -> Dict:
        """获取指定角色(monkey/horse)的提供者配置"""
        role_config = self._data.get(role, {})
        provider_name = role_config.get("provider", "openai")
        provider_defaults = self._data.get("providers", {}).get(provider_name, {})

        # Resolve API key: 环境变量 > DB多维表格 > YAML占位符
        api_key = role_config.get("api_key") or provider_defaults.get("api_key", "")
        if not api_key or api_key.startswith("YOUR_"):
            db_key = self._get_key_from_db(role)
            if db_key:
                api_key = db_key

        return {
            "name": provider_name,
            "api_key": api_key,
            "base_url": role_config.get("base_url") or provider_defaults.get("base_url", ""),
            "model": role_config.get("model", ""),
            "temperature": role_config.get("temperature", 0.7),
            "max_tokens": role_config.get("max_tokens", 4096),
            "is_local": provider_defaults.get("local", False),
        }

    def to_dict(self) -> Dict:
        return self._deep_copy(self._data)

    @staticmethod
    def _deep_copy(d):
        import copy
        return copy.deepcopy(d)

    @staticmethod
    def _deep_merge(base, override):
        """递归合并字典"""
        for key, val in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                Config._deep_merge(base[key], val)
            elif val is not None and val != "":
                base[key] = val

    @staticmethod
    def _set_nested(d, path, val):
        """设置嵌套字典值"""
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = val


def load_config(config_path: Optional[str] = None, **overrides) -> Config:
    """加载配置的快捷方式"""
    return Config(config_path, **overrides)
