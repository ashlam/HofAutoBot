# 绿联云 NAS 部署说明

适用于 x86_64 架构的 Linux 系统 NAS（如绿联 DX4600 / DXP4800 等系列）。

## 环境要求

- NAS 已安装 Docker（绿联云 UGOS / UGOS Pro 一般自带 Docker 管理器）
- NAS 能访问外网（用于构建镜像、下载 ChromeDriver）
- 已配置好 `configs/server_01/account_config.json` 等账号信息

## 快速开始（推荐）

把代码放到 NAS 上后，直接执行一键脚本：

```bash
bash scripts/deploy_nas.sh --server-id 1
```

脚本会自动：
1. 检查 Docker 是否可用
2. 构建 `hofautobot:latest` 镜像
3. 停止并删除同名旧容器（如果有）
4. 启动新容器，挂载 `configs/` 和 `logs/`

## 手动部署步骤

### 1. 进入项目目录

```bash
cd /path/to/HofAutoBot
```

### 2. 配置账号信息

确保 `configs/server_01/account_config.json` 存在且正确。如果 Windows 上已有，可直接复制到 NAS：

```bash
scp configs/server_01/account_config.json root@your-nas-ip:/path/to/HofAutoBot/configs/server_01/
```

### 3. 构建 Docker 镜像

```bash
docker build -t hofautobot:latest .
```

### 4. 启动容器

```bash
docker run -d \
  --name hofautobot-s1 \
  --restart unless-stopped \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/logs:/app/logs \
  hofautobot:latest --server-id 1
```

如果要跑 2 服，再起一个容器：

```bash
docker run -d \
  --name hofautobot-s2 \
  --restart unless-stopped \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/logs:/app/logs \
  hofautobot:latest --server-id 2
```

## 常用管理命令

### 查看日志

```bash
docker logs -f hofautobot-s1
```

### 查看运行状态

```bash
docker exec hofautobot-s1 python scripts/start_up_cli.py --status --server-id 1
```

### 停止容器

```bash
docker stop hofautobot-s1
docker rm hofautobot-s1
```

### 进入容器调试

```bash
docker exec -it hofautobot-s1 bash
```

## 更新代码/重启

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker build -t hofautobot:latest .

# 重启容器
docker stop hofautobot-s1
docker rm hofautobot-s1
bash scripts/deploy_nas.sh --server-id 1
```

## 常见问题

### 1. 构建时下载依赖很慢

Dockerfile 使用了 `docker.m.daocloud.io` 镜像源，如果 NAS 访问慢，可以编辑 `Dockerfile` 第一行，换成官方源：

```dockerfile
FROM python:3.9-slim-bookworm
```

### 2. ChromeDriver 下载失败

`webdriver_manager` 需要访问 Google 的 Chrome for Testing 服务。如果 NAS 网络受限，可以在 Windows 本机下载好对应 Linux 版本的 chromedriver，放到 `drivers/chrome/<version>/chromedriver-linux64/chromedriver`，然后挂载进容器：

```bash
-v $(pwd)/drivers:/app/drivers
```

或者把 chromedriver 直接复制到容器内的 `/usr/local/bin/chromedriver`。

### 3. 验证码识别失败

确保 `tesseract-ocr` 和 `tesseract-ocr-eng` 已安装（Dockerfile 已包含）。可以在容器内测试：

```bash
docker exec hofautobot-s1 tesseract --version
```

### 4. 游戏页面加载超时

检查 NAS 是否能正常访问游戏服务器地址，必要时在容器内测试：

```bash
docker exec hofautobot-s1 curl -I <游戏URL>
```

## 文件说明

- `Dockerfile`：NAS/服务器专用镜像构建文件
- `scripts/deploy_nas.sh`：一键部署脚本
- `configs/server_01/`：1 服配置目录
- `configs/server_02/`：2 服配置目录
- `logs/`：运行日志输出目录
