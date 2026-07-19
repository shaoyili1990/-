# Windows 代码签名指南

## 为什么会被拦截？

Windows 对所有**未签名**的可执行文件显示"Windows 已保护你的电脑"或"无法验证发布者"。
这不是病毒，是**签名缺失**——就像没有身份证的人过安检会被拦下来问话。

SmartScreen 的判定逻辑：
- **有知名 CA 签名** → 绿标，直接运行
- **有自签名证书** → 黄标，点"仍要运行"即可
- **无签名** → 红标（当前情况），需要点"更多信息 → 仍要运行"

## 解决方案（按推荐排序）

### 方案 1：Azure Trusted Signing ⭐ （最适合开源项目）

微软为开源项目提供**免费**的代码签名服务。

```bash
# 1. 安装 Azure CLI
# 2. 创建 Trusted Signing 账户
az trusted-signing create \
  --resource-group mygroup \
  --account-name MonkeyHarnessSign

# 3. 在 CI 中签名
- name: Sign Windows binaries
  uses: azure/trusted-signing-action@v0.3
  with:
    azure-tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    azure-client-id: ${{ secrets.AZURE_CLIENT_ID }}
    azure-client-secret: ${{ secrets.AZURE_CLIENT_SECRET }}
    endpoint: https://wus.codesigning.azure.net
    code-signing-account-name: MonkeyHarnessSign
    certificate-profile-name: PublicTrust
    files: dist/monkey-harness-agent.exe
```

优势：免费、受微软信任、可在 CI 中自动执行
条件：需要 Azure 订阅（免费即可）

### 方案 2：购买代码签名证书 💰

| CA | 价格/年 | 类型 |
|----|---------|------|
| DigiCert | ~$300 | EV（最高信任级别） |
| Sectigo | ~$200 | OV（组织验证） |
| Certum | ~$100 | OV/EV |

EV 证书可以直接绕过 SmartScreen，安装后即受信任。

### 方案 3：自签名证书（免费，但仍有警告）

```powershell
# 生成自签名证书
New-SelfSignedCertificate -Type Custom \
  -Subject "CN=Monkey Harness Agent" \
  -KeyUsage DigitalSignature \
  -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3") \
  -CertStoreLocation "Cert:\CurrentUser\My"

# 签名 exe
signtool sign /fd SHA256 /a /f mycert.pfx /p mypassword dist/monkey-harness-agent.exe
```

缺点：用户电脑不信任你的自签名证书，警告仍然存在，只是换了个措辞

### 方案 4：NSIS 安装器（当前已实现）

安装包（`.exe` 安装器）比裸 `.exe` 更不容易触发 SmartScreen。
用户只需运行 `MonkeyHarness-Setup-0.1.0.exe`，安装后程序自动加入开始菜单。

## ✅ 短期 vs 长期

| 阶段 | 方案 | 状态 |
|------|------|------|
| **现在** | NSIS 安装器（已集成到 CI） | ✅ 已完成 |
| **短期** | 在 README 和 Release 页面写清楚"点更多信息 → 仍要运行" | ✅ 已说明 |
| **长期** | 申请 Azure Trusted Signing 免费签名 | 📝 需要进行 |
