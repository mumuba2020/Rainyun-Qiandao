# Rainyun-Qiandao-V2 (Selenium)

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/scfcn/Rainyun-Qiandao/rainyun-sign.yml?style=flat-square)
![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg?style=flat-square)
![License](https://img.shields.io/badge/license-GPL%20v3.0-green.svg?style=flat-square)
![GitHub Stars](https://img.shields.io/github/stars/scfcn/Rainyun-Qiandao?style=flat-square)
![GitHub Forks](https://img.shields.io/github/forks/scfcn/Rainyun-Qiandao?style=flat-square)

## Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=scfcn/Rainyun-Qiandao&type=Date)](https://star-history.com/#scfcn/Rainyun-Qiandao&Date)

## 项目概述

Rainyun-Qiandao-V2 是一个基于 Selenium 和 ICR（Image Captcha Recognition）的雨云自动签到工具，通过模拟浏览器操作和高级验证码识别，实现雨云账户的自动每日签到以赚取积分。

## 功能特性

![Features](https://img.shields.io/badge/features-15+-orange.svg?style=flat-square)

- ✅ 自动完成雨云账户登录
- ✅ 使用 ICR 模块进行验证码自动识别（旋转分析+模板匹配）
- ✅ 支持Cookie缓存免密登录，跳过验证码
- ✅ 随机浏览器指纹（窗口尺寸+User-Agent），降低被检测风险
- ✅ 支持自定义随机延时（5-20秒），避免被系统识别为自动化脚本
- ✅ 支持在本地环境和 GitHub Actions 中运行
- ✅ 集成 webdriver-manager 自动匹配 ChromeDriver
- ✅ 详细的日志记录，便于排查问题
- ✅ 支持多账户签到，每个账户独立运行，互不干扰
- ✅ 支持并发处理多账户（可配置并发数）
- ✅ 失败自动重试机制，账户处理完成后统一重试
- ✅ 支持统一通知，汇总所有账户签到结果
- ✅ 支持7种通知推送方式（Push+、SMTP、Bark、钉钉、飞书、Telegram、Server酱）
- ✅ 支持自动更新功能，检测到新版本或版本过低时自动同步

## 技术栈

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-4.27+-43B02A?style=flat-square&logo=selenium&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.9+-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![Chrome](https://img.shields.io/badge/Chrome-Latest-4285F4?style=flat-square&logo=google-chrome&logoColor=white)

- Python 3.9+
- Selenium WebDriver 4.27+
- ICR 验证码识别模块（旋转分析+模板匹配）
- OpenCV 图像处理
- Google Chrome 浏览器

## 安装步骤

### 1. 环境要求

![Requirements](https://img.shields.io/badge/requirements-Python%203.9%2B%20Chrome-blue.svg?style=flat-square)

- Python 3.9 或更高版本
- Google Chrome 浏览器

### 2. 克隆项目

```bash
git clone https://github.com/scfcn/Rainyun-Qiandao.git
cd Rainyun-Qiandao
```

### 3. 安装依赖

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 配置 ChromeDriver

本项目已集成自动匹配 ChromeDriver 的功能，无需手动下载和配置。工具将按以下顺序尝试：

1. 使用 webdriver-manager 自动安装匹配的 ChromeDriver
2. 使用系统路径中的 ChromeDriver
3. 尝试常见的备用路径

## 使用方法

### 本地运行

#### 方法一：通过环境变量配置

##### 单账户配置

```bash
# Windows (PowerShell)
$env:RAINYUN_USER = "your_username"
$env:RAINYUN_PASS = "your_password"

# Linux/macOS
export RAINYUN_USER="your_username"
export RAINYUN_PASS="your_password"

# 运行脚本
python rainyun.py
```

##### 多账户配置

支持多行格式，每行一个用户名/密码，数量需匹配：

```bash
# Windows (PowerShell)
$env:RAINYUN_USER = "user1`nuser2`nuser3"
$env:RAINYUN_PASS = "pass1`npass2`npass3"

# Linux/macOS
export RAINYUN_USER="user1\nuser2\nuser3"
export RAINYUN_PASS="pass1\npass2\npass3"

# 运行脚本
python rainyun.py
```

#### 方法二：通过 .env 文件配置（推荐）

创建 `.env` 文件（已添加到 .gitignore）：

```env
RAINYUN_USER=your_username
RAINYUN_PASS=your_password
DEBUG=false
HEADLESS=false
AUTO_UPDATE=true
```

多账户配置：

```env
RAINYUN_USER=user1
user2
user3
RAINYUN_PASS=pass1
pass2
pass3
DEBUG=false
HEADLESS=false
AUTO_UPDATE=true
```

### 使用 GitHub Actions 自动签到

![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-2088FF?style=flat-square&logo=github-actions&logoColor=white)

1. Fork 本仓库
2. 进入仓库的 `Settings` > `Secrets and variables` > `Actions`
3. 添加以下密钥：

| Secret名称 | 说明 | 必需 |
|-----------|------|------|
| RAINYUN_USER | 雨云用户名（支持多行，每行一个用户名） | ✅ |
| RAINYUN_PASS | 雨云密码（支持多行，每行一个密码，需与用户名数量匹配） | ✅ |

4. 可选的通知推送配置：

| Secret名称 | 说明 | 推送方式 |
|-----------|------|----------|
| PUSH_PLUS_TOKEN | Push+用户令牌 | 微信 |
| PUSH_PLUS_USER | Push+群组编码（可选） | 微信 |
| SMTP_SERVER | SMTP服务器地址 | 邮件 |
| SMTP_SSL | 是否使用SSL (true/false) | 邮件 |
| SMTP_EMAIL | 邮箱地址 | 邮件 |
| SMTP_PASSWORD | 邮箱密码 | 邮件 |
| SMTP_NAME | 发件人姓名 | 邮件 |
| BARK_PUSH | Bark设备码或完整URL | iOS |
| DD_BOT_SECRET | 钉钉机器人密钥 | 钉钉 |
| DD_BOT_TOKEN | 钉钉机器人令牌 | 钉钉 |
| FSKEY | 飞书Webhook密钥 | 飞书 |
| TG_BOT_TOKEN | Telegram机器人令牌 | Telegram |
| TG_USER_ID | Telegram用户ID | Telegram |
| PUSH_KEY | Server酱密钥 | Server酱 |

5. 工作流将每天 UTC 4 点（UTC+8 12点）自动运行，也可以手动触发

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必需 |
|--------|------|--------|------|
| RAINYUN_USER | 雨云用户名（支持多行，每行一个用户名） | - | ✅ |
| RAINYUN_PASS | 雨云密码（支持多行，每行一个密码，需与用户名数量匹配） | - | ✅ |
| HEADLESS | 是否以无头模式运行（true/false） | false | ❌ |
| DEBUG | 是否启用调试模式（true/false） | false | ❌ |
| AUTO_UPDATE | 是否启用自动更新（true/false） | true | ❌ |
| USE_COOKIE | 是否启用Cookie缓存免密登录（true/false） | true | ❌ |
| MAX_WORKERS | 最大并发线程数 | 账户数量 | ❌ |
| GITHUB_ACTIONS | 在 GitHub Actions 环境中自动设置为 true，用于强制无头模式 | false | ❌ |

### 关键设置

- 随机延时设置为 5-20 秒，可在代码中调整
- 超时时间设置为 15 秒，可在代码中修改
- 验证码识别使用 ICR 模块，支持旋转分析和模板匹配

## 自动更新功能

脚本支持自动更新功能，可以检测到新版本或版本过低时自动同步到最新版本。

### 更新触发条件

- 发现新版本（`LATEST_VERSION > ver`）
- 版本过低（`ver < MIN_VERSION`）

### 更新方式

1. **优先使用 Git 同步**（如果系统已安装 Git）
   - 执行 `git fetch --all` 获取最新代码
   - 执行 `git reset --hard origin/main` 强制同步到最新版本

2. **Git 失败时回退到直接下载**
   - 从 GitHub 下载最新版本的 `rainyun.py` 文件
   - 覆盖当前文件

3. **下载失败时提示手动更新**
   - 显示更新地址，引导用户手动更新

### 配置方式

通过环境变量 `AUTO_UPDATE` 控制：

```bash
# 启用自动更新（默认）
export AUTO_UPDATE=true

# 禁用自动更新
export AUTO_UPDATE=false
```

或在 `.env` 文件中配置：

```env
AUTO_UPDATE=true
```

### 更新流程

```
🔄 开始自动更新到 v2.4...
📥 正在使用 git 同步最新版本...
✅ 更新完成！已同步到 v2.4
📝 请重新运行脚本以使用新版本
```

### 远程配置

脚本会从远程配置文件获取版本信息和更新地址：

```json
{
  "enabled": true,
  "min_version": "2.2",
  "latest_version": "2.4",
  "update_url": "https://github.com/scfcn/Rainyun-Qiandao"
}
```

## 常见问题

### 1. Linux 系统怎么使用？

参考 [Linux 环境配置指南](https://github.com/SerendipityR-2022/Rainyun-Qiandao/issues/1#issuecomment-3096198779)。

### 2. 找不到元素或等待超时，报错 `NoSuchElementException`/`TimeoutException`

- 网页加载缓慢，尝试延长超时等待时间
- 更换连接性更好的网络环境
- 确认 Chrome 浏览器版本与系统兼容

### 3. 验证码识别失败

ICR 模块使用旋转分析和模板匹配算法，识别率较高。脚本会自动重试，多次尝试后通常能成功通过验证。

### 4. 依赖安装失败

确保 Python 版本为 3.9+，使用以下命令安装依赖：

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果遇到依赖冲突，可以尝试：

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## GitHub Actions 优化

项目已集成 GitHub Actions 缓存功能，以加快每次运行的速度，主要缓存：

- Python 依赖
- Chrome 浏览器

## 版本历史

### v2.4 (2026-02-12)

- ✨ 新增自动更新功能，支持 Git 同步和直接下载
- ✨ 支持版本过低时自动更新

### v2.3 (2026-02-11)

- ✨ 新增 ICR 验证码识别模块（旋转分析+模板匹配）
- ✨ 支持多账户签到
- ✨ 集成 7 种通知推送方式
- 🐛 修复 wait 变量作用域问题
- 🐛 修复 ChromeDriver 执行格式错误
- 🐛 修复依赖冲突问题
- 📝 更新 GitHub Actions 配置

## 贡献指南

欢迎提交 Issue 和 Pull Request 来改进本项目：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个 Pull Request

## 许可证

![License](https://img.shields.io/badge/license-GPL%20v3.0-green.svg?style=flat-square)

本项目采用 GNU GENERAL PUBLIC LICENSE 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 免责声明

- 本工具仅用于学习和个人使用
- 使用本工具应遵守雨云官方的用户协议和相关规定
- 作者不对因使用本工具可能产生的任何后果负责

## 鸣谢

- [SerendipityR-2022](https://github.com/SerendipityR-2022) - 项目初始版本
- [Selenium](https://www.selenium.dev/) - 自动化测试工具
- [webdriver-manager](https://github.com/SergeyPirogov/webdriver_manager) - ChromeDriver 自动管理工具
- [OpenCV](https://opencv.org/) - 开源计算机视觉库

---

![GitHub last commit](https://img.shields.io/github/last-commit/scfcn/Rainyun-Qiandao?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/scfcn/Rainyun-Qiandao?style=flat-square)
![GitHub closed issues](https://img.shields.io/github/issues-closed/scfcn/Rainyun-Qiandao?style=flat-square)