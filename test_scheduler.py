"""Test idle scheduler + purchaser integration"""
import time, json, urllib.request, threading, sys

sys.path.insert(0, '/home/user/work/hermes-agent-universal')
import uvicorn
from hermes_universal.agent import HermesAgent
from hermes_universal.desktop.app import create_app

agent = HermesAgent()
app = create_app(agent)

t = threading.Thread(target=lambda: uvicorn.run(app, host='0.0.0.0', port=9099, log_level='error'), daemon=True)
t.start()
time.sleep(10)

tests = []
errors = []

def test(name, ok, detail=""):
    if ok:
        tests.append(f"  ✅ {name}" + (f" - {detail}" if detail else ""))
    else:
        errors.append(f"  ❌ {name}" + (f" - {detail}" if detail else ""))

# 1. Scheduler status
resp = urllib.request.urlopen('http://localhost:9099/api/scheduler/status')
d = json.loads(resp.read())
test("调度器状态IDLE", d['state'] == 'IDLE', f"state={d['state']}")
test("调度器运行中", d['is_running'] == True, f"running={d['is_running']}")
test("空闲阈值20分钟", d['config']['idle_threshold_minutes'] == 20)

# 2. mark-activity
req = urllib.request.Request('http://localhost:9099/api/scheduler/mark-activity', data=b'{}', method='POST')
resp = urllib.request.urlopen(req)
d2 = json.loads(resp.read())
test("标记活动", d2.get('ok') == True)

# 3. organize
req = urllib.request.Request('http://localhost:9099/api/purchaser/organize', data=b'{}', method='POST')
resp = urllib.request.urlopen(req)
d3 = json.loads(resp.read())
test("整理", d3.get('ok') == True, d3.get('message', ''))

# 4. inspect
resp = urllib.request.urlopen('http://localhost:9099/api/market/inspect')
d4 = json.loads(resp.read())
test("巡检", 'updates' in d4, f"{len(d4['updates'])}个更新")

# 5. search-by-need
req = urllib.request.Request('http://localhost:9099/api/market/search-by-need',
    data=json.dumps({'requirement':'搜索网页内容'}).encode(),
    headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
d5 = json.loads(resp.read())
test("采购员AI匹配", d5.get('total', 0) > 0, f"{d5['total']}个Skill")

# 6. categories
resp = urllib.request.urlopen('http://localhost:9099/api/market/categories')
d6 = json.loads(resp.read())
test("市场分类", len(d6) >= 6, f"{len(d6)}个分类")

# 7. installed
resp = urllib.request.urlopen('http://localhost:9099/api/market/installed')
d7 = json.loads(resp.read())
test("已安装Skill", isinstance(d7, list), f"{len(d7)}个")

# 8. Scheduler state machine after activity
resp = urllib.request.urlopen('http://localhost:9099/api/scheduler/status')
d8 = json.loads(resp.read())
test("标记后空闲重置", d8['idle_seconds'] < 5, f"idle={d8['idle_seconds']}s")

print("\n===== 空闲调度器 + 采购员系统 验证 =====")
print()
for t in tests:
    print(t)
if errors:
    print()
    for e in errors:
        print(e)
print()
if not errors:
    print("🎉 全部通过！")
else:
    print(f"⚠️  {len(errors)}/{len(tests)+len(errors)} 失败")

print()
print("=== 空闲调度器三定律 ===")
print("  1. 空闲≥20min → 自动整理")
print("  2. 整理后10min → 自动巡检")
print("  3. 用户活动(对话/任何操作) → 重置空闲计时")
print()
print("=== 猿+采购协同 ===")
print("  猴子(LLM)评估Skill更新 → 采购员执行安装")
print("  猴子识别需求 → 采购员AI搜索匹配Skill")
