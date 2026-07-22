"""
输出引擎测试 — workspace/output + 迭代版本控制
"""
import sys, os, json, shutil, tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

_TMP = ROOT / "test_data" / "workspace_test"
_TASK_COUNTER = [0]


def _unique_task_id() -> str:
    _TASK_COUNTER[0] += 1
    return f"T{_TASK_COUNTER[0]:03d}"


def _temp_db() -> tuple:
    """创建临时数据库引擎"""
    from harness_core.engine import EngineDB, seed_engine_db
    tmpdir = Path(tempfile.mkdtemp())
    engine_db = tmpdir / "engine.db"
    cog_db = tmpdir / "cog.db"
    db = EngineDB(engine_path=str(engine_db), cognition_path=str(cog_db))
    seed_engine_db(db)
    return db, tmpdir


def setup_module():
    _TMP.mkdir(parents=True, exist_ok=True)


def teardown_module():
    if _TMP.exists():
        shutil.rmtree(_TMP)


class TestOutputEngine:
    """workspace/output 文件系统引擎测试"""

    def test_init_workspace(self):
        from harness_core.tools.output_engine import init_workspace
        path = init_workspace(str(_TMP))
        assert Path(path).exists()
        readme = Path(path) / "_README.md"
        assert readme.exists()
        assert "弼马温" in readme.read_text(encoding="utf-8")

    def test_save_and_read_files(self):
        from harness_core.tools.output_engine import save_output_to_files, read_version_files
        output_root = str(_TMP / "output")
        tid = _unique_task_id()
        files = {"01_问题": "如何融合三作世界观", "02_推理过程": "第1步 识别核心矛盾", "03_输出结果": "## 小说设定"}
        created = save_output_to_files(output_root, tid, "v1", files, "初版")
        assert len(created) == 4
        loaded = read_version_files(output_root, tid, "v1")
        assert loaded["01_问题"] == "如何融合三作世界观"

    def test_version_dirs(self):
        from harness_core.tools.output_engine import save_output_to_files, read_version_files, list_task_versions
        output_root = str(_TMP / "output")
        tid = _unique_task_id()
        save_output_to_files(output_root, tid, "v1", {"01_问题": "Q1原始"})
        save_output_to_files(output_root, tid, "v2", {"01_问题": "Q2修订版"}, "甲方反馈")
        v1 = read_version_files(output_root, tid, "v1")
        v2 = read_version_files(output_root, tid, "v2")
        assert v1["01_问题"] == "Q1原始"
        assert v2["01_问题"] == "Q2修订版"
        assert list_task_versions(output_root, tid) == ["v1", "v2"]

    def test_iteration_input_build(self):
        from harness_core.tools.output_engine import build_iteration_input
        prev = {"01_问题": "原始三条铁律", "02_推理过程": "推理:无惨死→鬼血失活", "03_输出结果": "小说大纲"}
        new_input = build_iteration_input(prev, "铁律1不成立,鬼在1918年全灭")
        assert "原始三条铁律" in new_input["01_问题"]
        assert "鬼在1918年全灭" in new_input["01_问题"]
        assert "推理:无惨死→鬼血失活" in new_input["01_问题"]

    def test_list_tasks(self):
        from harness_core.tools.output_engine import list_all_tasks
        output_root = str(_TMP / "output")
        tasks = list_all_tasks(output_root)
        assert len(tasks) >= 1


class TestOutputDB:
    """多维表格输出管理测试 — 每个测试独立临时DB"""

    def test_output_templates_seeded(self):
        db, tmpdir = _temp_db()
        try:
            templates = db.list_output_templates()
            assert len(templates) >= 6
            types = [t["task_type"] for t in templates]
            assert "创作" in types
            assert "编程" in types
            assert "默认" in types
        finally:
            shutil.rmtree(tmpdir)

    def test_get_template_by_type(self):
        db, tmpdir = _temp_db()
        try:
            schema = db.get_output_template("创作")
            assert len(schema) == 3
            assert schema[0] == "01_问题"
            assert schema[2] == "03_输出结果"
        finally:
            shutil.rmtree(tmpdir)

    def test_get_template_fallback(self):
        db, tmpdir = _temp_db()
        try:
            schema = db.get_output_template("未知类型_xxx")
            assert schema == ["01_问题", "02_推理过程", "03_输出结果"]
        finally:
            shutil.rmtree(tmpdir)

    def test_task_output_save_and_read_db(self):
        db, tmpdir = _temp_db()
        try:
            tid = _unique_task_id()
            db.save_task_output(tid, "v1", "01_问题", "问题A")
            db.save_task_output(tid, "v1", "02_推理过程", "推理B")
            db.save_task_output(tid, "v2", "01_问题", "修订后问题")

            outputs = db.get_task_outputs(tid)
            assert len(outputs) == 3

            v1s = db.get_task_outputs(tid, "v1")
            assert len(v1s) == 2

            versions = db.get_task_versions(tid)
            assert "v1" in versions
            assert "v2" in versions
        finally:
            shutil.rmtree(tmpdir)

    def test_version_suggestion(self):
        db, tmpdir = _temp_db()
        try:
            new_tid = _unique_task_id()
            assert db.suggest_next_version(new_tid) == "v1"
            db.save_task_output(new_tid, "v1", "01_问题", "test")
            assert db.suggest_next_version(new_tid) == "v2"
        finally:
            shutil.rmtree(tmpdir)
