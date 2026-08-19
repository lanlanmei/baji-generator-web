# 吧唧生成器 Web V1

公开网页测试版：上传图片、圆形裁切、选择七种表面效果/三种包边/十一种背景，使用 V2.0 固定 OBJ 白模生成 1024 PNG 和 640 GIF，并提供 ZIP 后备下载。

## Windows 本地启动

需要 Python 3.10+。在项目目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

浏览器打开 <http://127.0.0.1:8000>。也可使用 Docker：

```powershell
docker compose up --build
```

## 测试

```powershell
python -m pytest -q
python -m unittest discover -s baji-generator-skill/tests -v
```

健康检查：`GET /health`。任务 API：`POST /api/jobs`、`GET /api/jobs/{id}` 及 PNG/GIF/ZIP 下载端点。

## 数据策略

上传图只在内存中解码，裁切图不永久保存；渲染产物按随机任务 ID 隔离到 `.data/jobs`，默认一小时后在后续请求时清理，也可主动删除。日志不记录图片内容或内部路径。生产环境不启用调试模式。
