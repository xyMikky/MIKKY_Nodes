# MIKKY Nodes 整合说明

本目录包含了所有ComfyUI插件的整合版本，所有节点都已统一添加MIKKY前缀，并归类到"MIKKY nodes"分类中。

## 📚 完整文档索引

| 快速链接 | 说明 |
|---------|------|
| [🎬 视频合并完整指南](VIDEO_MERGE_GUIDE.md) | ⭐⭐⭐ **concat_copy 方法 - 彻底解决静止帧问题** |
| [🎉 v2.1 更新说明](UPDATE_v2.1.md) | ⭐ **最新** - 短视频/片尾处理改进 |
| [🔧 短视频/片尾问题排查](TROUBLESHOOTING_SHORT_VIDEOS.md) | 1-2秒短视频合并问题解决方案 |
| [🔥 静止帧修复](HOTFIX_static_frames.md) | 静止帧问题的技术说明 |

## 文件列表

1. `01_average_split_node.py` - window frames平均分段计算节点
2. `02_batch_utils.py` - 批次工具节点（Stride、Fusion），用于图像的重叠（重叠后方便观察所有帧中水印遮罩的固定位置）
3. `03_frame_aligner.py` - 视频帧与音频同步节点，将视频输出帧率与音频帧率对齐
4. `05_imagejudge.py` - 图像尺寸限制节点（Lanczos）
5. `07_mask_batcher.py` - 遮罩批处理节点
6. `08_video_iterator.py` - 视频迭代器节点（搭配MIKKY Extract Storyboards节点使用）
7. `09_wan_image_viewer.py` - 图像查看选择器节点
8. `10_mask_editor.py` - 遮罩编辑器节点（视频遮罩编辑微调节点）
9. `11_banana_utils.py` - Banana局部重绘工具节点（Smart Crop、Uncrop Paste）
10. `12_extract_float.py` - 文本浮点数提取节点
11. `14_mikky_image.py` - 条件图像输入节点（若加载图像，则输出该图像，若不加载，则输出空值）
12. `15_video_seg.py` - 视频分段切片节点
14. `17_split_options.py` - 音频分段切片节点
15. `18_image_resize_duplicate.py` - 图像批量缩放复制节点
16. `19_video_side_splitter.py` - 视频左右拆分节点
17. `20_storyboard_extractor.py` - 故事板提取节点（关键帧提取，支持图像和音频分析）
18. `21_savelogs.py` - 保存日志列表节点（将字符串列表保存为多个文本文件）
19. `22_load_images_from_folder.py` - 从文件夹加载图像节点（输出图像列表和文件名）
20. `23_video_merger.py` - **视频合并节点（合并多个帧率不一致的视频文件）** ⭐ NEW

## 文件结构

```
MIKKY_Nodes/
├── __init__.py                    # Python节点自动加载文件
├── js/                            # JavaScript UI扩展文件
│   ├── __init__.js               # JS文件说明
│   ├── 01_mask_editor.js         # 遮罩编辑器UI
│   ├── 02_wan_image_viewer.js    # Wan图像查看器UI
│   └── 03_conditional_image_input.js  # 条件图像输入UI
├── 01_average_split_node.py      # Python节点文件
├── 02_batch_utils.py
├── ... (其他节点文件)
└── README.md                      # 本文件
```

## 使用方法

### 🚀 快速安装（推荐）

插件已配置为**完全自动化**安装模式！

**安装步骤：**
1. 将整个 `MIKKY_Nodes` 文件夹复制到 ComfyUI 的 `custom_nodes` 目录
2. 启动 ComfyUI
   - ComfyUI 会自动检测 `requirements.txt`
   - 自动安装所有依赖包（imageio, ffmpeg 等）
   - **无需手动安装 FFmpeg！** 🎉
3. 重启 ComfyUI（如果需要）
4. 所有节点将自动加载，可在节点菜单的 `MIKKY nodes` 分类下找到

### 📦 自动依赖安装

包含的 `requirements.txt` 会自动安装：
- ✅ **imageio** - 视频处理
- ✅ **imageio-ffmpeg** - 自动下载 FFmpeg
- ✅ **ffmpeg-python** - FFmpeg Python 绑定
- ✅ **numpy** - 数值计算
- ✅ **Pillow** - 图像处理

详细安装说明请参考 **[INSTALLATION.md](INSTALLATION.md)**  
依赖包详细说明请参考 **[DEPENDENCIES.md](DEPENDENCIES.md)**

**当前包含的节点数量：** 20 个节点文件（23+ 个节点），涵盖图像处理、视频处理、音频处理、遮罩编辑等多个功能领域。

### JS文件使用说明

JS文件位于 `js/` 目录下，用于增强某些节点的UI功能：

- `01_mask_editor.js` - 遮罩编辑器UI增强
- `02_wan_image_viewer.js` - Wan图像查看器UI
- `03_conditional_image_input.js` - 条件图像输入UI

`__init__.py` 中已设置 `WEB_DIRECTORY = "./js"`，ComfyUI会自动加载这些文件。

## 节点命名规则

- 所有节点类名都已添加 `MIKKY` 前缀
- 所有节点显示名都已添加 `MIKKY` 前缀
- 所有节点分类都统一为 `"MIKKY nodes"`，并进一步细分为子分类（如 `"MIKKY nodes/Utils"`、`"MIKKY nodes/Video Segment"` 等）

详细的节点分类列表请参考 [CATEGORIES.md](CATEGORIES.md)

## ⭐ 重要特性

### 新增：视频合并节点（v2.1）

**MIKKY Video Merger** - 专为处理不同帧率的视频段而设计！

✨ **v2.1 新特性：短视频处理改进**
- ✅ **修复片尾合并问题** - 1-2秒的短视频/片尾现在可以正确显示
- ✅ **彻底解决静止帧问题** - 不再出现视频结尾大量静止画面
- ✅ **完美音画同步** - 使用 MPEG-TS 流式拼接技术
- ✅ **零编码损失** - 全程不重新编码，保持原始质量
- ✅ **详细日志输出** - 实时显示每个视频的处理状态和文件大小

适用场景：
- ✅ 合并 for 循环生成的多个视频段
- ✅ 自动处理帧率不一致的视频（15fps、30fps、24fps 等）
- ✅ 避免手动在 PR/AE 中合并的繁琐步骤
- ✅ 无需手动安装 FFmpeg

详细使用指南请参考 **[VIDEO_MERGE_GUIDE.md](VIDEO_MERGE_GUIDE.md)**

## 注意事项

1. ✅ **依赖已自动安装** - ComfyUI 会在首次启动时自动安装所有依赖
2. ✅ **FFmpeg 自动集成** - 无需手动安装 FFmpeg
3. ⚠️ 某些节点可能需要额外的依赖（如 VHS 等，会在节点说明中标注）
4. 📝 如果遇到导入错误，请参考 [INSTALLATION.md](INSTALLATION.md) 或 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 故障排除

### MIKKY Mask Editor 节点无法使用

如果MIKKY Mask Editor节点的UI无法正常显示，请检查：

1. **JS文件路径**：确保 `__init__.py` 中设置了 `WEB_DIRECTORY = "./js"`
2. **节点名称匹配**：Python和JS中的节点名称必须完全一致（`MIKKYMaskEditorNode`）
3. **浏览器控制台**：打开开发者工具查看是否有错误信息或调试日志

详细故障排除指南请参考 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

