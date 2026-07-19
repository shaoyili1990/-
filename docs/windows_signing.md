# Windows 数字签名方案调研（2025年7月）

## 核心需求
- 优先免费（不绑信用卡、稳定）
- 备选付费（支持微信/支付宝）
- 稳定性第一，性价比第二

## 方案对比

| 方案 | 费用 | 支持微信/支付宝 | 稳定性 | SmartScreen | 优先级 |
|:-----|:----:|:---------------:|:------:|:-----------:|:------:|
| **SignTool + 自签名** | 🆓 免费 | — | ⭐⭐ | ❌ 弹窗警告 | ❌ P0 |
| **Azure Trusted Signing** | 🆓 免费(基础额度) | ❌ 需国际卡 | ⭐⭐⭐⭐⭐ | ✅ 信任 | ✅ **P0** |
| **SSL.com Code Signing** | ~$299/年 | ❌ 国际卡 | ⭐⭐⭐⭐ | ✅ 信任 | ❌ P3 |
| **Sectigo (Comodo)** | ~$230/年 | ❌ 国际卡 | ⭐⭐⭐⭐ | ✅ 信任 | ❌ P3 |
| **Certum Code Signing** | ~$169/年 | ❌ 国际卡 | ⭐⭐⭐⭐ | ✅ 信任 | ❌ P3 |
| **DigiCert EV** | ~$500/年 | ❌ 国际卡 | ⭐⭐⭐⭐⭐ | ✅ 立即信任 | ❌ 太贵 |
| **OpenSourceSign** (开源) | 🆓 | — | ⭐⭐ | ❌ 需社区背书 | ✅ P1 |

## 推荐排序

### P0: Azure Trusted Signing（最佳选择）
- **费用**: 免费额度足够个人项目使用
- **认证**: 微软官方签名服务，签名后立刻被Windows信任
- **注册**: 需要Azure账号（国际信用卡验证，新账号有免费额度）
- **操作**: `SignTool sign /fd SHA256 /a /td SHA256 /tr http://timestamp.acs.microsoft.com /v "file.exe"`
- **优点**: 企业级信任、自动时间戳、免费
- **缺点**: 需国际信用卡注册Azure

### P1: Open Source Signing (开源项目免费)
- 如果Hermes是开源项目，可通过 Open Source Signing 等社区服务申请免费签名
- 需证明项目是真正的开源项目

### P2: Certum（最优付费选择）
- 最便宜的商业签名（~$169/年）
- 标准代码签名证书
- 可通过代购渠道支持支付宝
- 需要营业执照或个体户证明

### P3: 其他商业方案
- SSL.com / Sectigo / DigiCert — 稳定但贵，且需国际卡

## 当前推荐执行方案

```
1. 尝试 Azure Trusted Signing（免费，需要Azure国际卡注册）
   → 注册Azure → 创建Trusted Signing账户 → 配置SignTool → 自动化签名

2. 如Azure无法注册（无国际卡），改用 Certum
   → 购买证书（~$169/年）→ 生成CSR → 签名 → 自动化打包流程

3. 纯免费兜底：SignTool + 自签名
   → 仅用于开发测试，不可用于公开发布
   → 用户会看到 SmartScreen 警告
```

## SignTool 命令行参考

```bash
# Azure Trusted Signing
SignTool sign /fd SHA256 /a /td SHA256 /tr http://timestamp.acs.microsoft.com /v "output.exe"

# 标准证书签名
SignTool sign /fd SHA256 /a /tr http://timestamp.digicert.com /v "output.exe"

# 自签名（测试用）
New-SelfSignedCertificate -Type CodeSigning -Subject "CN=Hermes" -CertStoreLocation Cert:\CurrentUser\My
SignTool sign /fd SHA256 /a /v "output.exe"
```
