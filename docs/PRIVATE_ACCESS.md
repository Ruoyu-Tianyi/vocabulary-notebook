# 手机和平板私人访问

## 工作方式

手机／平板 → HTTPS 自定义域名（Vercel）→ Tailscale Funnel → 本机学习网关 127.0.0.1:1401 → 词汇本 127.0.0.1:1400。

词库、复习记录、AI 凭据仍保存在电脑，Drive 同步继续工作。电脑必须开机、联网并运行两个服务；关机、休眠或断网期间无法远程学习。本方案不提供离线写入。浏览器可添加到主屏幕快捷访问。

DNS 可继续由阿里云管理。仅新增学习子域名，不修改已有网站解析。隐藏网址不能替代登录保护。

## 本机准备

先按 README 安装主程序，再安装网关：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-remote.txt
.\.venv\Scripts\python.exe configure_remote.py --email "你的邮箱" --origin "https://words.your-domain.cn"
```

配置工具生成随机密码，将密码摘要和会话密钥保存在 `.secrets/remote-access.json`，初始登录信息保存在 `.secrets/remote-login.txt`。保存到自己的密码管理器后，可删除后者。配置已存在时拒绝覆盖，日常更新不会重置密码。邮箱是账号标识，不发送验证码。

不要提交、分享或上传 `.secrets`。更换密码时停止网关、备份原配置后重新生成，已有会话随密钥更换而失效。

先启动词汇本，再启动网关：

```powershell
.\.venv\Scripts\python.exe remote_gateway.py
```

网关仅开放词汇、单词本和复习接口。模型设置、Drive 配置、备份、凭据及本机管理接口不可远程访问。登录有效期 7 天，使用 Secure、HttpOnly、SameSite Cookie；登录尝试限制为每 10 分钟 10 次。默认不启动公网入口。

## Tailscale 与 Vercel

1. 安装官方 Tailscale，使用自己的账号登录并授权当前电脑。Funnel 提供 HTTPS 公网入口，手机不必安装 Tailscale。
2. 首次启用 Funnel 可能要求在浏览器确认。只代理受保护的 **1401**，不得代理管理服务 1400。
3. 用 Tailscale 显示的固定 `设备名.网络名.ts.net` 主机名填写本机配置的 `tunnel_hostname`，重启网关。先确认未登录无法读取学习接口，再启用代理。
4. 创建独立 Vercel 项目，将全部路径代理到固定 Funnel 域名。不部署本机数据库、配置文件或 API Key。
5. 在 Vercel 项目绑定学习子域名，按平台返回的实际记录值手动添加 DNS。不要直接将自定义域名指向 *.ts.net，其证书不覆盖你的域名。
6. 从自定义域名登录，验证添加、释义、检索、复习和退出。代理与隧道的可用性、延迟和使用限制需要在实际网络中验证。

常用命令（以安装版本帮助为准）：

```powershell
 tailscale status
 tailscale funnel --bg http://127.0.0.1:1401
 tailscale funnel status
 tailscale funnel reset
```

后台 Funnel 可在重启后恢复，词汇本与网关也必须启动。未配置自动启动时，开机后分别启动这两个服务。停止 Funnel 撤销公网转发；停止网关不会删除词库。

## 验收与维护

- 未登录访问 API 返回 401，页面引导登录；登录后才能读取或修改词库。
- 错误密码、伪造或过期会话不能访问；模型和同步设置即使登录也不能远程操作。
- 添加后本机显示同一条记录，复习记录也一致。用测试词验证后可自行删除。
- 关闭服务器时远程不可用，恢复后重新连接。
- 更新使用 README 的无损流程，保留 `.secrets/remote-access.json`，不要重新初始化。

高级部署也可使用 Cloudflare Access：网关保留 issuer、audience、email 签名验证模式。需另行配置身份策略和隧道，不与密码模式字段混用。
