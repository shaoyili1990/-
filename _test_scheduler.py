"""验证空闲调度器全链路"""
import time, json, urllib.request, threading, uvicorn, sys
from hermes_universal.agent import HermesAgent
from hermes_universal.desktop.app import create_app

print("[启动] 创建agent和app...")
agent = HermesAgent()
app = create_app(agent)

t = threading.Thread(target=lambda: uvicorn.run(app, host='0.0.0.0', port=9099, log_level='error'), daemon=True)
t.start()
print("[启动] 等待服务就绪...")
time.sleep(10)

results = []

# 1. 调度器状态
resp = urllib.request.urlopen('http://localhost:9099/api/scheduler/status')
d = json.loads(resp.read())
assert d['state'] == 'IDLE'
assert d['is_running'] == True
results.append(f'✅ 调度器: {d["state"]} | 运行中={d["is_running"]} | 空闲{d["idle_seconds"]}s')

# 2. mark-activity
req = urllib.request.Request('http://localhost:9099/api/scheduler/mark-activity', data=b'{}', method='POST')
json.loads(urllib.request.urlopen(req).read())
results.append('✅ 标记活动: 重置空闲计时')

# 3. 整理
req = urllib.request.Request('http://localhost:9099/api/purchaser/organize', data=b'{}', method='POST')
d = json.loads(urllib.request.urlopen(req).read())
results.append(f'✅ 整理: {d["message"]}')

# 4. 巡检
resp = urllib.request.urlopen('http://localhost:9099/api/market/inspect')
d = json.loads(resp.read())
results.append(f'✅ 巡检: {len(d["updates"])}个待更新')

# 5. AI按需搜索
req = urllib.request.Request('http://localhost:9099/api/market/search-by-need', 
    data=json.dumps({'requirement':'需要搜索网页和抓取内容的工具'}).encode(), 
    headers={'Content-Type':'application/json'})
d = json.loads(urllib.request.urlopen(req).read())
results.append(f'✅ 采购员AI匹配: 找到{d["total"]}个匹配Skill')

# 6. 市场分类
resp = urllib.request.urlopen('http://localhost:9099/api/market/categories')
results.append(f'✅ 市场分类: {len(json.loads(resp.read()))}个分类')

# 7. 已安装
resp = urllib.request.urlopen('http://localhost:9099/api/market/installed')
results.append(f'✅ 已安装Skill: {len(json.loads(resp.read()))}个')

print("\n===== 验证结果 =====")
for r in results:
    print(r)

print("\n===== 调度器状态机 =====")
print("""
  ┌──────────┐   空闲≥20min    ┌────────────┐
  │   IDLE   │ ──────────────→ │ ORGANIZING │
  │  空闲待命 │                 │   整理中    │
  └────┬─────┘                 └──────┬──────┘
       ↑                              │ 整理完成
       │                        ┌─────▼──────┐
       │                        │  COOLDOWN   │ 冷却10min
       │                        │  整理后冷却  │
       │                        └─────┬──────┘
       │                              │ 冷却结束
       │                        ┌─────▼───────┐
       │                        │  INSPECTING  │
       │                        │    巡检中     │
       │                        └─────┬───────┘
       │                              │
       │             ┌────────────────┼────────────┐
       │             ▼                           ▼
       │     ┌──────────────┐           ┌──────────────┐
       │     │  EVALUATING  │ 有更新    │  回到 IDLE   │ 无更新
       │     │  猴采购评估   │           │              │
       │     └──────┬───────┘           └──────────────┘
       │            │ 评估完成
       └────────────┘
""")
print("三定律:")
print("  1. 空闲≥20分钟 → 自动整理(清理孤儿Skill/去重)")
print("  2. 整理后10分钟冷却 → 自动巡检(对比市场版本)")
print("  3. 用户发送消息 → 自动mark-activity(重置空闲计时)")
print()
print("猿采购协同:")
print("  猴子(LLM)评估更新是否采纳 → 采购员执行安装或跳过")
