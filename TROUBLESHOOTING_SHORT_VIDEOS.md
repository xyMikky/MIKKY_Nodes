# 🔧 短视频片段合并问题排查

## 问题描述

用户反馈：添加1秒的片尾视频时出现问题：
- ❌ 片尾没有正确显示
- ❌ 片尾的画面变成了上一段视频的最后一帧
- ❌ 片尾内容丢失

**示例场景：**
```
视频1: 10秒正常内容
视频2: 8秒正常内容  
视频3: 1秒片尾（logo、致谢等）← 这个没有正确显示
```

---

## 根本原因

### 1. MPEG-TS 转换问题
短视频（<2秒）在转换为 MPEG-TS 格式时可能遇到：
- **时间戳精度问题**：1秒的视频可能只有几帧（15fps = 15帧，30fps = 30帧）
- **GOP 边界**：如果 GOP size 设置过大（如 250 帧），1秒视频可能只有一个不完整的 GOP
- **Muxer 缓冲**：FFmpeg 的 muxer 可能因缓冲策略导致短视频数据丢失

### 2. h264_mp4toannexb 过滤器失败
某些视频编码格式可能不兼容 `h264_mp4toannexb` 过滤器：
- HEVC (H.265) 需要使用 `hevc_mp4toannexb`
- 某些特殊编码可能不需要此过滤器
- 转换失败时，生成的 TS 文件可能为空或损坏

### 3. 拼接时的边界问题
当最后一个 TS 文件很小时：
- `concat:` protocol 可能不正确处理文件结尾
- 时间戳可能未正确延续
- 最后几帧可能被截断

---

## 解决方案（v2.1 更新）

### 改进1: 更robust的 TS 转换

**原代码问题：**
```python
cmd = [ffmpeg, "-i", video, "-c", "copy", 
       "-bsf:v", "h264_mp4toannexb", "-f", "mpegts", output]
```

**新代码改进：**
```python
cmd = [
    ffmpeg,
    "-i", video,
    "-map", "0:v:0",  # 显式映射视频流
    "-map", "0:a:0",  # 显式映射音频流（如果有）
    "-c:v", "copy",
    "-c:a", "copy",
    "-bsf:v", "h264_mp4toannexb",
    "-f", "mpegts",
    "-muxdelay", "0",      # ← 关键：禁用 mux 延迟
    "-muxpreload", "0",    # ← 关键：禁用预加载
    "-y", output
]
```

**关键参数说明：**
- **`-muxdelay 0`**: 禁用 muxer 的延迟缓冲，确保数据立即写入
- **`-muxpreload 0`**: 禁用预加载，避免短视频被缓冲丢失
- **`-map 0:v:0` / `-map 0:a:0`**: 显式指定要映射的流，避免自动选择错误

### 改进2: 文件验证

每个 TS 文件生成后立即验证：
```python
if os.path.exists(temp_video) and os.path.getsize(temp_video) > 0:
    video_streams.append(temp_video)
    print(f"✓ 成功（大小: {os.path.getsize(temp_video) / 1024:.1f} KB）")
else:
    print(f"❌ 生成的文件为空")
    raise Exception("生成的 TS 文件为空")
```

### 改进3: 降级策略

如果 `h264_mp4toannexb` 失败，自动尝试简化命令：
```python
if result.returncode != 0:
    print("⚠️ h264_mp4toannexb 失败，尝试不使用 bsf")
    cmd_simple = [ffmpeg, "-i", video, "-c", "copy", 
                  "-f", "mpegts", "-muxdelay", "0", 
                  "-muxpreload", "0", "-y", output]
    result = subprocess.run(cmd_simple)
```

### 改进4: 使用 concat demuxer 而非 concat protocol

**原方案（concat protocol）：**
```bash
ffmpeg -i "concat:video_001.ts|video_002.ts|video_003.ts" output.mp4
```
- 问题：可能不正确处理最后一个文件的结尾

**新方案（concat demuxer + 列表文件）：**
```bash
# concat_list.txt:
file 'C:/path/to/video_0000.ts'
file 'C:/path/to/video_0001.ts'
file 'C:/path/to/video_0002.ts'

ffmpeg -f concat -safe 0 -i concat_list.txt output.mp4
```
- 优势：更可靠地处理所有文件，包括最后一个

---

## 验证和调试

### 检查生成的 TS 文件

如果合并后片尾丢失，检查临时文件夹（合并前）：
```
ComfyUI/output/videos/temp_concat/
├── video_0000.ts  ← 第一段
├── video_0001.ts  ← 第二段
└── video_0002.ts  ← 片尾（检查这个文件）
```

**检查命令：**
```bash
# 检查文件大小
dir temp_concat

# 播放单个 TS 文件
ffplay video_0002.ts

# 检查文件信息
ffprobe -v error -show_format -show_streams video_0002.ts
```

### 常见问题诊断

#### 问题1: TS 文件为空或很小（<10KB）
```
[MIKKYVideoMerger]   ✓ 成功（大小: 2.3 KB）  ← 异常小！
```

**可能原因：**
- 原视频已损坏
- 编码格式不兼容
- FFmpeg 转换失败但未报错

**解决方法：**
```bash
# 手动测试转换
ffmpeg -i your_1s_video.mp4 -c copy -f mpegts test.ts

# 如果失败，尝试重新编码
ffmpeg -i your_1s_video.mp4 -c:v libx264 -c:a aac -f mpegts test.ts
```

#### 问题2: h264_mp4toannexb 报错
```
[h264_mp4toannexb @ ...] Packet header is not contained in global extradata
```

**原因：** 视频不是 H.264 编码，或者已经是 Annex B 格式

**解决方法：** 节点会自动尝试不使用 bsf 的简化方式

#### 问题3: 片尾音频缺失
```
[MIKKYVideoMerger] 警告: 视频 ending.mp4 没有音频流
```

**解决方法：** 
- 如果片尾本来就没有音频（纯图片视频），这是正常的
- 如果需要音频，确保原视频包含音频轨道

---

## 推荐的片尾制作方式

### 方法1: 使用足够的帧率
```python
# 1秒片尾，建议至少 30fps
帧数 = 30 帧（30fps × 1秒）

# 如果是静态图片，使用 FFmpeg 生成：
ffmpeg -loop 1 -i ending.png -c:v libx264 -t 1 -pix_fmt yuv420p ending.mp4
```

### 方法2: 稍微延长片尾时长
```python
# 从 1 秒改为 2 秒，更稳定
duration = 2  # 秒
```

### 方法3: 确保片尾编码一致
```python
# 片尾使用与主视频相同的编码参数
ffmpeg -i ending_source.mp4 \
  -c:v libx264 \
  -preset medium \
  -crf 18 \
  -pix_fmt yuv420p \
  -r 30 \  # 帧率与主视频一致
  -c:a aac \
  -b:a 192k \
  ending.mp4
```

---

## 测试步骤

### 1. 单独验证片尾视频
```python
# 在 ComfyUI 中单独加载片尾视频
# 确保它能正常播放
```

### 2. 使用详细日志
```python
# 节点现在会输出详细信息：
[MIKKYVideoMerger]   处理 3/3: ending.mp4
[MIKKYVideoMerger]   ✓ 成功（大小: 125.3 KB）  # 检查大小是否合理
[MIKKYVideoMerger] 成功处理 3 个视频片段
[MIKKYVideoMerger] 拼接列表:
[MIKKYVideoMerger]   1. video_0000.ts
[MIKKYVideoMerger]   2. video_0001.ts
[MIKKYVideoMerger]   3. video_0002.ts  # 确认片尾被包含
```

### 3. 检查最终输出
```bash
# 使用 FFprobe 检查时长
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output.mp4

# 预期: 10 + 8 + 1 = 19 秒
# 实际: 应该接近 19 秒
```

---

## 已知限制

### 非常短的视频（<0.5秒）
- **可能存在问题**：少于 15 帧的视频可能无法正确处理
- **建议**：片尾至少 1 秒，最好 2 秒

### 纯图片视频（无关键帧）
- **可能存在问题**：某些只有 I-frame 的视频可能需要特殊处理
- **建议**：生成片尾时使用正常的 GOP 结构

### HEVC (H.265) 编码
- **可能存在问题**：需要使用 `hevc_mp4toannexb` 而非 `h264_mp4toannexb`
- **建议**：目前节点会自动降级到简化方式，应该可以工作

---

## 更新历史

- **v2.1 (2026-01-09)**: 
  - 添加 `-muxdelay 0` 和 `-muxpreload 0` 参数
  - 改用 concat demuxer + 列表文件
  - 添加文件大小验证
  - 改进错误日志
  
- **v2.0 (2026-01-09)**: 引入 concat_copy 方法

---

## FAQ

**Q: 为什么片尾变成了上一段的最后一帧？**  
A: 这是因为 TS 文件生成失败或为空，拼接时 FFmpeg 延续了前一个视频的最后一帧。新版本会验证每个 TS 文件的大小。

**Q: 如何确认片尾是否正确处理？**  
A: 查看日志中的 `✓ 成功（大小: X KB）`，确保片尾的 TS 文件大小合理（至少几十 KB）。

**Q: 可以使用静态图片作为片尾吗？**  
A: 可以，但需要先用 FFmpeg 转换为视频格式（见上文"推荐的片尾制作方式"）。

---

**最后更新**: 2026-01-09  
**状态**: ✅ v2.1 已修复  
**作者**: MIKKY Nodes Team
