"""
FingerprintLoader 测试 — 思维指纹加载与领域匹配
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestFingerprintLoader:
    """指纹加载器测试"""

    def test_thinker_fingerprint_exists(self):
        """thinker_unified_fingerprint.json 应存在且有效"""
        fp_path = ROOT / "fingerprints" / "thinker_unified_fingerprint.json"
        assert fp_path.exists(), "指纹文件应存在"
        with open(fp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["name"] == "thinker", f"名称应为 thinker, 实际为 {data['name']}"
        assert "top10" in data, "应有 top10 权重"
        assert len(data["top10"]) == 10, f"top10 应为10条, 实际 {len(data['top10'])}"
        print(f"✅ Thinker指纹: {len(data['top10'])} 条top链")

    def test_domain_fingerprints_referencing_thinker(self):
        """所有领域指纹应引用 thinker_unified"""
        domain_dir = ROOT / "fingerprints"
        for fpath in sorted(domain_dir.glob("domain_*.json")):
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            based_on = data.get("based_on", "")
            assert "thinker" in based_on, \
                f"{fpath.name} 的 based_on 应引用 thinker, 实际: {based_on}"
        print(f"✅ 所有领域指纹正确引用 thinker")

    def test_no_jiapo_remaining(self):
        """确认无一贾珀引用残留"""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "贾珀", "fingerprints/"],
            capture_output=True, text=True, cwd=ROOT
        )
        assert result.returncode != 0, f"仍有贾珀引用: {result.stdout[:200]}"
        print(f"✅ 无贾珀残留")

    def test_monkey_loads_fingerprint(self):
        """指纹文件可直接通过JSON加载"""
        import json
        fp_path = ROOT / "fingerprints" / "thinker_unified_fingerprint.json"
        assert fp_path.exists(), "thinker指纹文件应存在"
        with open(fp_path, "r", encoding="utf-8") as f:
            fp = json.load(f)
        assert isinstance(fp, dict), "应返回 dict"
        assert "top10" in fp, "应有 top10"
        assert fp["name"] == "thinker", f"名称应为 thinker, 实际 {fp['name']}"
        print(f"✅ 指纹文件: thinker（{len(fp['top10'])} top链）")

    def test_domain_fp_file_count(self):
        """领域指纹应≥8个"""
        domain_dir = ROOT / "fingerprints"
        files = list(domain_dir.glob("domain_*.json"))
        assert len(files) >= 8, f"应≥8个领域指纹, 实际 {len(files)}"
        print(f"✅ 领域指纹: {len(files)} 个")


class TestSubchainSystem:
    """子链系统测试"""

    def test_subchains_loaded(self):
        """子链目录应有文件"""
        subchains_dir = ROOT / "subchains"
        md_files = list(subchains_dir.glob("*.md"))
        assert len(md_files) >= 100, f"子链模板应≥100条, 实际 {len(md_files)}"
        print(f"✅ 子链模板: {len(md_files)} 条")

    def test_subchain_dir_structure(self):
        """子链目录应有 .md 文件"""
        assert (ROOT / "subchains").is_dir()
        # 统计文件数
        md_files = list((ROOT / "subchains").rglob("*.md"))
        assert len(md_files) >= 100, f"应≥100.md文件, 实际 {len(md_files)}"
        print(f"✅ 子链文件: {len(md_files)} 个")
