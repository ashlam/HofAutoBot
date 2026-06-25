#!/usr/bin/env bash
# 绿联云 NAS 一键部署脚本（x86_64 Linux）
# 用法：bash scripts/deploy_nas.sh [--server-id 1] [--name hofautobot-s1] [--build-only]

set -e

SERVER_ID=1
CONTAINER_NAME=""
BUILD_ONLY=false

show_help() {
    cat <<EOF
用法: bash scripts/deploy_nas.sh [选项]

选项:
  --server-id ID    服务器编号，默认 1
  --name NAME       容器名称，默认 hofautobot-s{server_id}
  --build-only      只构建镜像，不启动容器
  -h, --help        显示帮助

示例:
  bash scripts/deploy_nas.sh
  bash scripts/deploy_nas.sh --server-id 2
  bash scripts/deploy_nas.sh --server-id 1 --name mybot
EOF
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --server-id)
            SERVER_ID="$2"
            shift 2
            ;;
        --name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

if [[ -z "$CONTAINER_NAME" ]]; then
    CONTAINER_NAME="hofautobot-s${SERVER_ID}"
fi

IMAGE_NAME="hofautobot:latest"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_ROOT"

echo "======================================"
echo "  HofAutoBot NAS 部署脚本"
echo "  项目目录: $PROJECT_ROOT"
echo "  服务器ID: $SERVER_ID"
echo "  容器名称: $CONTAINER_NAME"
echo "  镜像名称: $IMAGE_NAME"
echo "======================================"

# 1. 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误：未找到 docker 命令，请先安装 Docker。"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "错误：Docker 服务未运行，或当前用户没有权限访问 Docker。"
    exit 1
fi

# 2. 检查必要配置
if [[ ! -f "configs/server_${SERVER_ID}/account_config.json" ]]; then
    echo "警告：configs/server_${SERVER_ID}/account_config.json 不存在，请先配置账号信息。"
fi

# 3. 构建镜像
echo ""
echo "[1/3] 构建 Docker 镜像..."
docker build -t "$IMAGE_NAME" .

if [[ "$BUILD_ONLY" == true ]]; then
    echo ""
    echo "镜像构建完成，已跳过容器启动。"
    echo "后续可手动运行："
    echo "  docker run -d --name $CONTAINER_NAME --restart unless-stopped \\"
    echo "    -v \$(pwd)/configs:/app/configs \\"
    echo "    -v \$(pwd)/logs:/app/logs \\"
    echo "    $IMAGE_NAME --server-id $SERVER_ID"
    exit 0
fi

# 4. 停止并删除旧容器
echo ""
echo "[2/3] 清理旧容器（如果存在）..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop "$CONTAINER_NAME" &> /dev/null || true
    docker rm "$CONTAINER_NAME" &> /dev/null || true
    echo "旧容器 $CONTAINER_NAME 已清理"
else
    echo "没有同名旧容器"
fi

# 5. 启动新容器
echo ""
echo "[3/3] 启动新容器..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -v "$(pwd)/configs:/app/configs" \
    -v "$(pwd)/logs:/app/logs" \
    "$IMAGE_NAME" --server-id "$SERVER_ID"

echo ""
echo "======================================"
echo "  部署完成"
echo "======================================"
echo "容器名称: $CONTAINER_NAME"
echo ""
echo "常用命令："
echo "  查看日志:    docker logs -f $CONTAINER_NAME"
echo "  查看状态:    docker exec $CONTAINER_NAME python scripts/start_up_cli.py --status --server-id $SERVER_ID"
echo "  停止容器:    docker stop $CONTAINER_NAME"
echo "  删除容器:    docker rm $CONTAINER_NAME"
echo ""
echo "5 秒后打印最近日志..."
sleep 5
docker logs --tail 30 "$CONTAINER_NAME"
