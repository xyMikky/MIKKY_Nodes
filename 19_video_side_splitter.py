import torch


class MIKKYVideoSideBySideSplitter:
    """
    功能：专用于处理左右分屏的对比视频。
    输入：一个视频（其实就是一堆图片帧的Batch）。
    输出：两个视频流（左半边画面的视频流，右半边画面的视频流）。
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),  # 这里接收的是视频的所有帧
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("left_video_frames", "right_video_frames")
    FUNCTION = "split_video_frames"
    CATEGORY = "MIKKY nodes/Video Utils"

    def split_video_frames(self, images):
        # images 的形状是 [Frame_Count, Height, Width, Channels]
        # Frame_Count 就是视频的总帧数

        height = images.shape[1]
        width = images.shape[2]

        # 计算宽度的中间点
        mid_point = width // 2

        # 核心逻辑：
        # 对于每一帧（:），保留高度（:），
        # 左边视频：宽度取从 0 到 中间点
        left_part = images[:, :, :mid_point, :]

        # 右边视频：宽度取从 中间点 到 最后
        right_part = images[:, :, mid_point:, :]

        # 返回两组帧，ComfyUI 会把它们识别为两个独立的视频流
        return (left_part, right_part)


# 节点映射
NODE_CLASS_MAPPINGS = {
    "MIKKYVideoSideBySideSplitter": MIKKYVideoSideBySideSplitter
}

# 节点显示名称映射
NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYVideoSideBySideSplitter": "MIKKY Split Video (Left/Right)"
}

