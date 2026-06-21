import torch


class MIKKYSyncVideoFrameToAudio:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),  # 输入的图片Batch
                "audio": ("AUDIO",),  # 输入的音频
            }
        }

    RETURN_TYPES = ("IMAGE", "FLOAT", "INT", "STRING")
    RETURN_NAMES = ("images", "fps", "frame_count", "debug_info")
    FUNCTION = "calculate_sync"
    CATEGORY = "MIKKY nodes/Audio Sync"

    def calculate_sync(self, images, audio):
        # 1. 获取图片总帧数
        # images shape通常是 [Batch, Height, Width, Channel]
        frame_count = images.shape[0]

        # 2. 解析音频数据
        # ComfyUI的标准音频格式是一个字典: {'waveform': tensor, 'sample_rate': int}
        waveform = audio['waveform']
        sample_rate = audio['sample_rate']

        # 获取总采样数 (waveform通常是 [Channels, Samples] 或 [Batch, Channels, Samples])
        # 我们取最后一个维度作为时间维度
        total_samples = waveform.shape[-1]

        # 3. 计算音频时长 (秒)
        duration_seconds = total_samples / sample_rate

        # 4. 计算目标FPS
        # 逻辑：要让 frame_count 张图正好播放 duration_seconds 秒
        # FPS = Frames / Time
        if duration_seconds <= 0.001:
            target_fps = 24.0  # 防止除以0，给个默认值
            print(f"Warning: Audio duration is almost zero ({duration_seconds}s). Defaulting to 24 FPS.")
        else:
            target_fps = frame_count / duration_seconds

        # 格式化调试信息
        info = (f"Frames: {frame_count}, Audio Duration: {duration_seconds:.4f}s, "
                f"Calculated FPS: {target_fps:.4f}")

        # 返回图片(透传), 计算出的FPS, 帧数, 调试信息
        return (images, float(target_fps), frame_count, info)


# 节点映射
NODE_CLASS_MAPPINGS = {
    "MIKKYSyncVideoFrameToAudio": MIKKYSyncVideoFrameToAudio
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYSyncVideoFrameToAudio": "MIKKY Sync Images to Audio (Auto FPS)"
}

