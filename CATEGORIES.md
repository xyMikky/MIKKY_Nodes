# MIKKY Nodes 分类说明

所有节点都在 "MIKKY nodes" 主分类下，按功能细分为以下子分类：

## 分类列表

### Utils（工具类）
- **MIKKY Average Split (≤90)** - 平均分割计算
- **MIKKY Extract Float from Text** - 文本浮点数提取

### Batch Utils（批次工具）
- **MIKKY Batch Image Stride** - 批次图像步进
- **MIKKY Batch Image Fusion** - 批次图像融合

### Image Transform（图像变换）
- **MIKKY Limit Image Max Size (Lanczos)** - 限制图像最大尺寸
- **MIKKY Image Resize & Duplicate** - 图像缩放和复制

### Image Input（图像输入）
- **MIKKY Conditional Image Input (with Reset Button)** - 条件图像输入
- **MIKKY Load Images From Folder** - 从文件夹加载图像（输出图像和文件名）

### Image Viewer（图像查看器）
- **MIKKY Wan Batch Gallery Selector** - Wan批次图库选择器

### Mask（遮罩处理）
- **MIKKY RGBO Mask Batcher + BBox** - 遮罩批处理和边界框

### Mask Editor（遮罩编辑器）
- **MIKKY Mask Editor** - 遮罩编辑器（带UI）

### Banana Utils（Banana工具）
- **MIKKY 🍌 Banana Smart Crop** - 智能裁切
- **MIKKY 🍌 Banana Uncrop Paste** - 智能回贴

### Audio Sync（音频同步）
- **MIKKY Sync Images to Audio (Auto FPS)** - 图像与音频同步

### Audio Segment（音频分段）
- **MIKKY SplitOptions: Segment Audio (Sync)** - 音频分段
- **MIKKY SplitOptions: Save Audio Segments** - 保存音频分段
- **MIKKY SplitOptions: Get Audio Segment** - 获取音频分段

### Video Iterator（视频迭代器）
- **MIKKY Folder Video Count** - 文件夹视频计数
- **MIKKY Video Info By Index** - 按索引获取视频信息
- **MIKKY Load Video From Path** - 从路径加载视频
- **MIKKY Save Video To Folder** - 保存视频到文件夹
- **MIKKY Load Video By Index** - 按索引加载视频

### Video Segment（视频分段）
- **MIKKY SplitOptions: Segment Video (Dynamic)** - 视频动态分段
- **MIKKY SplitOptions: Save Segments (VHS)** - 保存视频分段（VHS）
- **MIKKY SplitOptions: Save Segments (Simple)** - 保存视频分段（简单）
- **MIKKY SplitOptions: Get Segment by Index** - 按索引获取分段
- **MIKKY SplitOptions: Segment Count** - 分段计数

### Video Utils（视频工具）
- **MIKKY Split Video (Left/Right)** - 视频左右分屏

### Storyboard（故事板）
- **MIKKY Extract Storyboards** - 提取故事板（关键帧）
- **MIKKY Int Batch** - 整数批次
- **MIKKY Int Batch Size** - 整数批次大小

### SiliconFlow（SiliconFlow工具）
- **MIKKY SiliconFlow Async Tagger** - 异步图像打标器

### File Utils（文件工具）
- **MIKKY Save Logs List** - 保存日志列表为多个文本文件

## 分类结构

```
MIKKY nodes/
├── Utils
├── Batch Utils
├── Image Transform
├── Image Input
├── Image Viewer
├── Mask
├── Mask Editor
├── Banana Utils
├── Audio Sync
├── Audio Segment
├── Video Iterator
├── Video Segment
├── Video Utils
├── Storyboard
├── SiliconFlow
└── File Utils
```

