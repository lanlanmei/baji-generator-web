# 新手部署说明

## 推荐：Render Blueprint（无需本机 Docker）

1. 把项目推送到 GitHub 或 GitLab 仓库。
2. 登录 Render，选择 **New → Blueprint** 并连接该仓库。
3. Render 会读取根目录的 `render.yaml`，在新加坡区域创建免费 Docker Web Service。
4. 部署完成后会得到 `https://baji-generator-web.onrender.com` 或带随机后缀的地址；以控制台实际显示为准。

免费实例空闲 15 分钟会休眠，第一次访问需要等待唤醒。若真实 GIF 渲染时内存不足，请把实例从 Free 升级到至少 2 GB 内存的付费规格。

## 最短方式：支持 Docker 的 HTTPS 平台

1. 把整个 `baji-generator-web` 文件夹上传到一个私有或公开 Git 仓库。
2. 在 Render、Railway、Fly.io 或其他支持 Docker 的平台新建 Web Service，连接仓库；平台会自动读取 `Dockerfile`。
3. 设置环境变量：`BAJI_WORKERS=1`、`BAJI_JOB_TTL=3600`、`BAJI_TEMP_DIR=/tmp/baji-jobs`。
4. 服务端口使用平台提供的 `PORT`；本项目已自动读取。
5. 部署完成后用平台分配的 HTTPS 地址访问，并打开 `/health` 确认返回 `{"status":"ok"...}`。

需要你登录或授权的步骤是第 2 步：授权托管平台读取 Git 仓库。不要把密钥写进仓库。

## 资源与存储

- 测试最低建议：2 vCPU、4 GB 内存、2 GB 临时磁盘；生产建议 4 vCPU、8 GB 内存。
- OBJ 渲染是 CPU 密集型，默认仅并发 1 个任务，其他任务排队，避免内存峰值。
- 任务文件是临时数据，不需要持久卷；实例重启后丢失属于预期行为。
- 如平台使用只读文件系统，把 `BAJI_TEMP_DIR` 指向 `/tmp/baji-jobs`。
- 公网必须使用平台托管 HTTPS；不要直接暴露开发服务器，也不要开启 FastAPI debug/reload。
- 多实例部署需要外部共享任务队列和对象存储，V1 单实例不包含 Redis。
