# 吧唧生成器 Skill V2.0

本地真实模型版渲染器，把 PNG/JPG/JPEG/WebP/GIF（GIF 第一帧）制作为带浅弧正面、极细卷边、内凹背壳和完整别针机构的 58mm 吧唧，并默认为每种效果额外输出旋转 GIF。单图最大 10MB，EXIF 自动纠正，透明输入保留 alpha。

## 安装

需要 Python 3.10+：`python -m pip install -r requirements.txt`。

PowerShell：

```powershell
python .\scripts\render_baji.py .\photo.png --effects star-holographic --rim gold --background light-gray --size 1024 --output .\outputs
```

通用终端：

```bash
python scripts/render_baji.py photo.png --effects glossy white-ceramic matte-frosted
python scripts/render_baji.py one.png two.jpg three.webp --effects fluffy-cookie --rim silver --background white
python scripts/render_baji.py photo.png --preset star-holographic --background pale-purple --backend auto
python scripts/render_baji.py photo.png --preset glossy --backend obj
python scripts/render_baji.py photo.png --backend pillow --no-animation
```

省略 `--effects` 会生成七种效果，每种默认输出 PNG + GIF。使用 `--no-animation` 只输出 PNG；`--animation` 可显式启用。动画参数为 `--animation-size 640 --animation-frames 58 --animation-duration 40`（毫秒/帧），独立于静态图尺寸。

V2.0 的 `assets/models/badge_master_58mm.obj` 是固定主模型：X 轴为厚度、+X 为正面，Y/Z 直径为 58mm。正面鼓包和内凹背壳由白模参数剖面逐像素求交；针、铰链、安装脚和卡扣使用 OBJ 三角面 z-buffer。静态 PNG 是同一模型的 0° 帧，GIF 只改变 yaw，因此模型、相机、贴图、材质和灯光完全一致。

模型分为 `front_art`、`rim_metal`、`back_metal`。六种特殊材质仅改变正面 UV 纹理与粗糙度/高光；银、金、黑只改变极细卷边；内凹背壳和全部硬件保持冷灰微亮不锈钢。世界空间反射来自曲面或三角网格法线，不烘焙到用户原图。

后端顺序：`blender`（发现可执行文件时无界面渲染）→ `obj`（包内固定白模的本地 CPU 3D，本机默认）→ `glb`（仅在有经验证的无界面 WebGL 运行时时）→ `pillow`（兼容模式）。明确指定不可用后端会返回清楚错误；`auto` 自动降级。Pillow 模式仍输出 PNG/GIF，但不宣称包含真实背面别针。

本测试机没有 Blender，因此实际验收使用本地 OBJ 3D 后端。实测 1024 静态约 2.2 秒，640×640、58 帧 GIF 约 60 秒；CPU 与输入图片会影响结果。

效果可用中文名或英文名。包边：`silver/gold/black` 或银色/金色/黑色。背景：`white/transparent/soft-black/light-gray/mist-pink/cream/sage/gray-blue/pale-yellow/soft-peach/pale-purple`，也支持需求中的中文名。尺寸只允许 1024/2048/4096。`--seed` 固定纹理，`--inner-border-color '#ffffff'` 设置内边，`--preview` 输出裁切诊断。输出重名自动编号。

运行测试：`python -m unittest discover -s tests -v`。V2.0 当前共 38 项测试；模型来源、材质分区及再生成说明见 `assets/models/MODEL_ASSET.md`。
