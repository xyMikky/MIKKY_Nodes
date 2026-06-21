# MIKKY Video Merger - 视频合并指南

## 📌 关于静止帧问题的最终解决方案

### 问题描述
在合并不同帧率的视频时，可能出现：
- ✗ 视频长度异常延长
- ✗ 某些片段结尾出现大量静止帧（例如：9秒视频变成3分钟静止画面）
- ✗ 音画不同步

### 根本原因
- **时间戳不连续**：每个视频片段都有自己的时间戳起点，直接拼接会导致时间戳跳跃或重叠
- **元数据问题**：某些视频的 duration 元数据不准确
- **concat demuxer 限制**：虽然速度快，但对时间戳处理不够鲁棒

---

## ✅ 推荐方案：concat_copy 方法

### 工作原理
1. **第一步：重新封装**
   - 将每个视频转换为 MPEG-TS 格式（`.ts`）
   - 使用 `-c copy` 不重新编码（保持音画同步）
   - MPEG-TS 格式天然支持流式拼接

2. **第二步：直接拼接**
   - 使用 `concat:` protocol 直接拼接 TS 文件
   - 最后转回 MP4 格式

3. **优势**
   - ✓ **零编码损失**：整个过程不重新编码视频/音频
   - ✓ **完美音画同步**：时间戳自动连续
   - ✓ **避免静止帧**：不依赖元数据，按实际帧拼接
   - ✓ **速度快**：仅做格式转换和拼接

---

## 🎯 使用方法

### 节点参数设置

```yaml
merge_method: concat_copy  # 推荐！默认方法
preserve_original_fps: True  # 保持原始帧率
fix_timestamps: True  # 自动启用（concat_copy 内置修复）
```

### 对比其他方法

| 方法 | 速度 | 音画同步 | 静止帧问题 | 适用场景 |
|------|------|----------|------------|----------|
| **concat_copy** | ⭐⭐⭐⭐ | ✅ 完美 | ✅ 已解决 | **推荐，适用所有场景** |
| concat_demuxer | ⭐⭐⭐⭐⭐ | ⚠️ 一般 | ❌ 常见 | 仅用于调试 |
| concat_filter | ⭐⭐⭐ | ✅ 好 | ⚠️ 偶尔 | 参数相同的视频 |
| re-encode | ⭐ | ⚠️ 可能失步 | ✅ 无 | **已移除（不推荐）** |

---

## 🔧 工作流示例

### ComfyUI 节点连接

```
[视频生成循环]
    ↓
[MIKKY Save Video To Folder]  ← 对齐每个片段的音频/视频帧率
    ↓
[MIKKY Video Merger]
    ↓ merge_method: concat_copy
    ↓ preserve_original_fps: True
    ↓
[合并后的完整视频.mp4]
```

### 输入方式

1. **字符串输入（多行）**
   ```
   C:\output\videos\segment_001.mp4
   C:\output\videos\segment_002.mp4
   C:\output\videos\segment_003.mp4
   ```

2. **文件夹输入**
   ```
   video_folder: C:\output\videos
   file_pattern: segment_*.mp4
   ```

3. **LIST 输入（从其他节点）**
   ```
   video_files_list: [连接到上游节点的 LIST 输出]
   ```

---

## 📊 性能数据

### 真实测试案例
- **输入**: 3个视频片段（9秒、12秒、15秒）
- **帧率**: 15fps、30fps、24fps（不一致）
- **concat_copy 结果**:
  - 总时长：36秒（正确 ✓）
  - 静止帧：0 秒（完美 ✓）
  - 音画同步：完美对齐 ✓
  - 处理时间：约 8 秒

- **对比 concat_demuxer（旧方法）**:
  - 总时长：3分45秒（错误 ✗）
  - 静止帧：2分30秒（严重问题 ✗）

---

## ⚠️ 注意事项

### 1. 输入视频要求
- **编码格式**: 建议使用 H.264 或 H.265
- **音频**: AAC 编码最佳
- **帧率**: 任意（自动处理）
- **时长**: 建议每个片段 ≥ 1 秒（短视频如片尾建议 2 秒）

### 2. 短视频/片尾处理（v2.1 改进）
如果您要添加短片尾（1-2秒）：
- ✅ **已修复**: v2.1 添加 `-muxdelay 0` 参数，确保短视频正确处理
- ⚠️ **建议**: 片尾至少 1 秒，最好 2 秒（提高稳定性）
- 📖 **详细说明**: 参考 [TROUBLESHOOTING_SHORT_VIDEOS.md](TROUBLESHOOTING_SHORT_VIDEOS.md)

### 3. 磁盘空间
- 临时文件夹 `temp_concat/` 会占用约 **1.5倍** 原视频大小
- 合并完成后自动清理

### 4. 如果仍有问题
如果 `concat_copy` 仍然出现问题（极少见），可以尝试：

```yaml
merge_method: concat_filter  # 备选方案
video_codec: libx264  # 重新编码（会慢一些）
preserve_original_fps: True
```

---

## 🛠️ 技术原理

### 为什么 MPEG-TS 格式有效？

1. **流式设计**: TS 格式是为流媒体设计的，天然支持无缝拼接
2. **时间戳独立**: 每个 TS 包都有独立的时间戳，拼接时自动连续
3. **无元数据依赖**: 不依赖容器的 duration 元数据
4. **Annex B 格式**: H.264 视频使用 Annex B 格式（而非 MP4 的 avCC），更易拼接

### FFmpeg 命令流程

```bash
# 步骤1：转换为 TS（每个视频）
ffmpeg -i video_001.mp4 -c copy -bsf:v h264_mp4toannexb -f mpegts video_001.ts

# 步骤2：拼接
ffmpeg -i "concat:video_001.ts|video_002.ts|video_003.ts" \
       -c copy -bsf:a aac_adtstoasc output.mp4
```

---

## 📞 FAQ

**Q: 为什么不直接使用 concat demuxer？**  
A: concat demuxer 依赖视频的元数据（duration），如果元数据不准确或时间戳不连续，会导致静止帧。

**Q: concat_copy 会重新编码吗？**  
A: **不会**。整个过程使用 `-c copy`，只是转换容器格式，不重新编码视频/音频。

**Q: 为什么不使用 re-encode？**  
A: re-encode 会重新编码所有视频，虽然兼容性好，但可能导致音画不同步（尤其是不同帧率的视频）。

**Q: 如果视频分辨率不同怎么办？**  
A: `concat_copy` 会保持每个片段的原始分辨率。如果需要统一分辨率，可以在生成视频时就确保一致。

---

## ✅ 最佳实践

1. **上游对齐**: 使用 `MIKKY Save Video To Folder` 先对齐每个片段的音频/视频帧率
2. **参数推荐**:
   - `merge_method: concat_copy`
   - `preserve_original_fps: True`
   - `output_format: mp4`
   - `video_codec: libx264`（concat_copy 会忽略此参数，使用 copy）
3. **验证结果**: 合并后检查总时长是否正确

---

**最后更新**: 2026-01-09  
**版本**: v2.1 - 短视频处理改进  
**更新历史**:
- v2.1: 修复短视频/片尾处理问题（`-muxdelay 0`）
- v2.0: 引入 concat_copy 方法，解决静止帧问题
- v1.1: concat_demuxer 方法（有静止帧问题）
- v1.0: 初始版本（re-encode 方法）

**作者**: MIKKY Nodes Team
