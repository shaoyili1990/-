# Windows 数字签名方案：SignPath Foundation 实战

> 📅 最后更新: 2026-07-19
> 当前阶段：**准备申请材料** → 提交 SignPath Foundation → 签名发布

## 方案选择：SignPath Foundation（最佳免费路径）

对于开源项目，**SignPath Foundation** 是当前最成熟、门槛最低的免费 Windows 代码签名方案。

| 要素 | SignPath Foundation | OSSign | 自签名 |
|:-----|:-------------------:|:------:|:------:|
| 费用 | ✅ **完全免费** | ✅ 免费 | 免费 |
| 信任级别 | ✅ **Windows信任**（签名链到可信CA） | ✅ 信任 | ❌ SmartScreen警告 |
| 需要个人ID | ❌ **不需要** — 验证仓库而非个人 | 可能需要 | — |
| 私钥管理 | ✅ **HSM云**，CI可调用 | HSM | 本地 |
| 中国可申请 | ✅ **是**，无需国际卡 | — | ✅ |
| CI集成 | ✅ GitHub Actions原生 | — | ❌ 手动 |
| 发布者名称 | ⚠️ 显示为 SignPath Foundation | OSSign | 你的名字 |

---

## 申请条件（来自 signpath.org/terms.html）

1. **OSI-approved 开源许可证**（MIT / Apache-2.0 / GPL 等）
2. **公共 GitHub 仓库**（源代码必须公开可访问）
3. **可免费下载的发布版**（GitHub Releases）
4. **代码签名策略页** — 在项目主页添加声明（见下方模板）
5. **CI 构建** — 必须从 GitHub Actions 构建并提交签名
6. **只签自己的项目** — 签名团队 = 开发维护团队 = 源码仓库所有者

---

## 第一步：在 README 中添加代码签名策略

```markdown
## 代码签名策略

本项目签名发布 Windows 构件。

✅ 免费代码签名由 [SignPath.io](https://signpath.io) 提供，证书来自 [SignPath Foundation](https://signpath.org)
✅ 提交者与审核者: [@shaoyili1990](https://github.com/shaoyili1990) (仓库Owner)
✅ 审批者: [@shaoyili1990](https://github.com/shaoyili1990)
✅ 隐私政策: 本程序不会将任何信息传输到其他联网系统，
   除非用户明确请求或操作需要
```

---

## 第二步：向 SignPath Foundation 提交申请

### 操作步骤

1. 访问 [signpath.org](https://signpath.org) → 点击 **Apply**
2. 填写申请表单：
   - **项目仓库 URL**：`https://github.com/shaoyili1990/-`
   - **许可证**：MIT
   - **发布版 URL**：`https://github.com/shaoyili1990/-/releases`
   - **项目描述**：`Monkey Harness Agent (弼马温) — AI多模态智能体和自治巡逻系统。`
   - **代码签名策略 URL**：`https://github.com/shaoyili1990/-#代码签名策略`
   - **你希望使用的证书发布者名称**：SignPath Foundation
3. 提交后等待审批（通常 1-2 周）
4. 审批通过后，SignPath 会通过邮件发送:
   - SignPath.io 组织 slug
   - 签名策略 slug
   - API Token（用于 GitHub Actions）

### 典型审批问题

| 常见问题 | 如何回答 |
|:---------|:---------|
| 证书发布者显示谁？ | SignPath Foundation（默认选项） |
| 需要个人验证吗？ | 不需要，验证仓库即可 |
| 项目是私有的吗？ | 必须是 **公开** 仓库 |

---

## 第三步：配置 GitHub Actions

审批通过后，配置 GitHub Actions 自动签名：

### 设置 Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 添加：

| Secret 名称 | 值来源 |
|:------------|:-------|
| `SIGNPATH_API_TOKEN` | SignPath 邮件中的 API Token |

### GitHub Actions 工作流

```yaml
# .github/workflows/sign-windows.yml
# 当创建 Release 时自动签名 Windows 构件
```

> 完整工作流已准备在 `.github/workflows/sign-windows.yml`
> 收到 API Token 后只需填入项目 slug 和签名策略 slug 即可启用。

---

## 第四步：打包构建

```bash
# 本地构建测试
python build.py

# 输出: dist/monkey-harness-agent.exe
# 提交到 GitHub Actions 后自动签名
```

> 完整打包脚本已准备在 `build.py`

---

## 审批等待期的临时方案

在等待 SignPath Foundation 审批期间（1-2 周），可使用自签名测试：

```powershell
# ⚠️ 自签名仅用于开发测试，正式发布请等 SignPath

# 1. 创建自签名证书
New-SelfSignedCertificate -Type CodeSigning `
  -Subject "CN=Monkey Harness Agent (Dev)" `
  -CertStoreLocation "Cert:\CurrentUser\My"

# 2. 签名
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert
Set-AuthenticodeSignature -FilePath "dist/monkey-harness-agent.exe" `
  -Certificate $cert -TimestampServer "http://timestamp.digicert.com"
```

---

## 备选方案

如果 SignPath Foundation 审批未通过：

| 方案 | 费用 | 信任 | 备注 |
|:-----|:----:|:----:|:-----|
| **OSSign** (ossign.org) | 免费 | ✅ 信任 | 同样针对开源项目，备选 |
| **Azure Trusted Signing** | ~$10/月 | ✅ **高信任** | 需国际卡注册 Azure |
| **自签名** | 免费 | ❌ SmartScreen 警告 | 需用户手动信任 |
| **Certum** ($169/年) | 付费 | ✅ 信任 | 可通过代购支付宝支付 |

---

## 文件清单

| 文件 | 说明 | 状态 |
|:-----|:-----|:-----|
| `docs/windows_signing.md` | 本文档 — 完整指南 | ✅ |
| `.github/workflows/sign-windows.yml` | GitHub Actions 签名工作流 | ✅ 待填项目slug |
| `build.py` | Windows 打包脚本 (PyInstaller) | ✅ |
| `README.md` | 需添加代码签名策略章节 | 📝 提交申请前 |
