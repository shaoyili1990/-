# Windows 数字签名方案：开源免费版

## 推荐方案：SignPath Foundation（最佳路径）

对于开源/测试版项目，**SignPath Foundation** 是当前最成熟、门槛最低的免费方案。

### 为什么选它

| 要素 | SignPath Foundation | OSSign | 自签名 |
|:-----|:-------------------:|:------:|:------:|
| 费用 | ✅ **完全免费** | ✅ 免费 | 免费 |
| 信任级别 | ✅ **Windows信任**（签名链到可信CA） | ✅ 信任 | ❌ SmartScreen警告 |
| 需要个人ID | ❌ **不需要** — 验证仓库而非个人 | 可能需要 | — |
| 私钥管理 | ✅ **HSM云端**，CI可调用 | HSM | 本地 |
| 中国可申请 | ✅ **是** | 可能 | ✅ |
| CI集成 | ✅ GitHub Actions原生 | 待确认 | ❌手动 |
| 发布者名称 | ⚠️ SignPath Foundation（非你的名字） | OSSign | 你的名字 |

### 申请条件

1. **OSI-approved 开源许可证**（MIT / Apache-2.0 / GPL 等）
2. **公共 GitHub 仓库**（源代码必须公开）
3. **可免费下载的发布版**（GitHub Releases 或官网）
4. **代码签名策略页** — 在项目主页添加声明
5. **CI构建** — 必须从CI（GitHub Actions）构建并提交签名

### 签名效果

- 签名发布者显示为：**SignPath Foundation**
- 二进制哈希关联到你的仓库地址
- Windows SmartScreen **不再警告**
- 用户可验证构件确实来自你的仓库

---

## 实施步骤

### 第一步：准备项目

```markdown
# 在 README 顶部添加"代码签名策略"章节

## 代码签名策略

本项目签名发布 Windows 构件。

✅ 免费代码签名由 SignPath.io 提供，证书来自 SignPath Foundation
✅ 维护团队: @shaoyili1990（仓库 Owner）
✅ 审批者: @shaoyili1990
✅ 隐私政策: 本程序不会将任何信息传输到其他联网系统，
   除非用户明确请求或操作需要
```

### 第二步：向 SignPath Foundation 提交申请

1. 访问 [signpath.org](https://signpath.org) → 点 **Apply**
2. 填写：
   - 项目仓库 URL：`https://github.com/shaoyili1990/-`
   - 许可证：MIT
   - 发布版 URL：GitHub Releases
   - 项目描述：AI Agent 自治调度与多门类巡检系统
3. 等待审批（通常 1-2 周）

### 第三步：配置 GitHub Actions 签名

```yaml
# .github/workflows/sign.yml
name: Sign Windows Release
on:
  release:
    types: [published]

jobs:
  sign:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build
        run: python build.py
        
      - name: Submit signing request to SignPath
        uses: signpath/github-action-submit-signing-request@v1
        with:
          api-token: ${{ secrets.SIGNPATH_API_TOKEN }}
          project-slug: hermes-agent
          signing-policy-slug: release-signing
          artifact-path: ./dist/hermes-setup.exe
          
      - name: Upload signed artifact
        uses: actions/upload-artifact@v4
        with:
          path: ./dist/hermes-setup-signed.exe
```

### 第四步：编写打包脚本

```bash
# install.py — 简单的 Windows 安装打包
# 将 hermes-agent 及其依赖打包为一个安装程序

# 使用 NSIS 或 Inno Setup（免费）创建安装包
# SignPath 将对生成的 .exe 进行签名
```

---

## 备选方案对比

### 如果 SignPath 审批不通过

| 方案 | 费用 | 信任 | 备注 |
|:-----|:----:|:----:|:-----|
| OSSign (ossign.org) | 免费 | ✅ 信任 | 同样针对开源项目 |
| Azure Trusted Signing | ~$10/月 | ✅ **高信任** | 需国际卡注册Azure账号 |
| 自签名 | 免费 | ❌ SmartScreen警告 | 需用户手动信任 |
| Certum ($169/年) | 付费 | ✅ 信任 | 可通过代购支付宝支付 |

### 临时方案（审批等待期）

```powershell
# 自签名（仅开发测试用）
New-SelfSignedCertificate -Type CodeSigning `
  -Subject "CN=Hermes Agent (Dev)" `
  -CertStoreLocation Cert:\CurrentUser\My

# 签名
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert
Set-AuthenticodeSignature -FilePath "dist/hermes-setup.exe" `
  -Certificate $cert -TimestampServer "http://timestamp.digicert.com"
```

---

## 关键文件变更

| 文件 | 操作 | 说明 |
|:-----|:----:|:-----|
| `README.md` | 新增 | 添加代码签名策略章节 |
| `.github/workflows/sign.yml` | 新增 | GitHub Actions 签名工作流 |
| `build.py` | 待创建 | Windows 打包脚本 |
| `docs/windows_signing.md` | 更新 | 此文档 |

---

## 总结

对测试版/Hermes当前阶段：

> 🎯 **SignPath Foundation → 免费 + 无需国际卡 + 无需营业执照 → 最佳路径**
>
> 审批期间可先用自签名过渡，发布后不产生任何费用。
