import torch
import os
import folder_paths
from typing import List, Tuple, Optional
import numpy as np
import re

# ==============================
# 尝试导入 VHS（用于高级视频保存节点，若未安装不影响简单节点使用）
# ==============================
VHS_AVAILABLE = False
try:
    from videohelpersuite.nodes import VideoCombine

    VHS_AVAILABLE = True
except ImportError:
    pass


# ==============================
# 核心分段节点：动态输出 IMAGE_LIST
# ==============================
class MIKKYVideoSegmentByKeyframesDynamic:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),  # [N, H, W, C]
                "keyframes": ("STRING", {"default": "0,30,78", "multiline": False}),
            },
        }

    RETURN_TYPES = ("IMAGE_LIST",)
    RETURN_NAMES = ("segments",)
    FUNCTION = "segment_video"
    CATEGORY = "MIKKY nodes/Video Segment"

    def segment_video(self, images: torch.Tensor, keyframes: str) -> Tuple[List[torch.Tensor],]:
        total_frames = images.shape[0]
        try:
            kf_list = [int(x.strip()) for x in keyframes.split(",") if x.strip()]
            kf_list = sorted(set(kf_list))
        except Exception as e:
            raise ValueError(f"Invalid keyframes format: {e}")

        if not kf_list:
            raise ValueError("At least one keyframe must be provided.")
        if kf_list[0] != 0:
            raise ValueError("First keyframe must be 0.")
        if any(kf < 0 or kf >= total_frames for kf in kf_list):
            raise ValueError(f"All keyframes must be in range [0, {total_frames - 1}]")

        boundaries = kf_list + [total_frames]
        segments = []
        for i in range(len(kf_list)):
            start = boundaries[i]
            end = boundaries[i + 1]
            if start < end:
                segments.append(images[start:end])
        if not segments:
            raise ValueError("No valid segments generated.")
        return (segments,)


# ==============================
# 保存节点（依赖 VHS，功能完整，未修改逻辑）
# ==============================
class MIKKYSaveVideoSegments:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "segments": ("IMAGE_LIST",),
                "filename_prefix": ("STRING", {"default": "segment"}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 120}),
                "format": (["video/h264-mp4", "video/h265-mp4", "image/gif", "image/webp"],),
                "pingpong": ("BOOLEAN", {"default": False}),
                "save_output": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "audio": ("VHS_AUDIO",),
            }
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "save_segments"
    CATEGORY = "MIKKY nodes/Video Segment"

    def save_segments(
            self,
            segments: List[torch.Tensor],
            filename_prefix: str,
            fps: int,
            format: str,
            pingpong: bool,
            save_output: bool,
            audio=None
    ):
        if not VHS_AVAILABLE:
            raise RuntimeError("ComfyUI-VideoHelperSuite is required for this node. Please install it.")

        output_dir = folder_paths.get_output_directory()
        seg_dir = os.path.join(output_dir, "video_segments")
        os.makedirs(seg_dir, exist_ok=True)

        saved_count = 0
        for idx, segment in enumerate(segments):
            if segment.shape[0] == 0:
                print(f"[MIKKYSaveVideoSegments] Skipping empty segment {idx}")
                continue

            try:
                filename = f"{filename_prefix}_{idx:04d}"
                
                # 创建 VideoCombine 实例（每次创建新的实例以确保状态干净）
                video_combine = VideoCombine()
                
                # 调用 combine_video 方法
                # 注意：VideoCombine 可能需要特定的参数格式，这里使用最简化的参数列表
                result = video_combine.combine_video(
                    images=segment,
                    frame_rate=fps,
                    loop_count=0,
                    filename_prefix=filename,
                    format=format,
                    pingpong=pingpong,
                    save_output=save_output,
                    quality=95,
                    audio=audio if audio is not None else None,
                    batch_manager=None,
                )

                # 检查结果并打印保存信息
                if isinstance(result, dict):
                    if "ui" in result:
                        if "video" in result["ui"]:
                            video_info = result["ui"]["video"]
                            if isinstance(video_info, list) and len(video_info) > 0:
                                video_path = video_info[0]
                                print(f"[MIKKYSaveVideoSegments] ✅ Saved segment {idx} to: {video_path}")
                                saved_count += 1
                            elif isinstance(video_info, str):
                                print(f"[MIKKYSaveVideoSegments] ✅ Saved segment {idx} to: {video_info}")
                                saved_count += 1
                            else:
                                print(f"[MIKKYSaveVideoSegments] ⚠️ Segment {idx}: video info format unexpected: {type(video_info)}")
                        else:
                            print(f"[MIKKYSaveVideoSegments] ⚠️ Segment {idx} processed but no 'video' key in UI result")
                            print(f"[MIKKYSaveVideoSegments] Available keys in UI: {list(result['ui'].keys())}")
                    else:
                        print(f"[MIKKYSaveVideoSegments] ⚠️ Segment {idx} processed but no 'ui' key in result")
                        print(f"[MIKKYSaveVideoSegments] Available keys: {list(result.keys())}")
                else:
                    print(f"[MIKKYSaveVideoSegments] ⚠️ Segment {idx} returned unexpected result type: {type(result)}")
                    print(f"[MIKKYSaveVideoSegments] Result: {result}")
                    
            except TypeError as e:
                # 参数错误，尝试使用更少的参数
                print(f"[MIKKYSaveVideoSegments] ⚠️ TypeError for segment {idx}, trying alternative method: {e}")
                try:
                    video_combine = VideoCombine()
                    # 尝试只传递最基本的参数
                    result = video_combine.combine_video(
                        images=segment,
                        frame_rate=fps,
                        filename_prefix=filename,
                        format=format,
                        save_output=save_output,
                    )
                    if isinstance(result, dict) and "ui" in result:
                        print(f"[MIKKYSaveVideoSegments] ✅ Saved segment {idx} (alternative method)")
                        saved_count += 1
                except Exception as e2:
                    print(f"[MIKKYSaveVideoSegments] ❌ Alternative method also failed for segment {idx}: {e2}")
            except Exception as e:
                print(f"[MIKKYSaveVideoSegments] ❌ Error saving segment {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"[MIKKYSaveVideoSegments] ✅ Successfully saved {saved_count}/{len(segments)} segments to: {seg_dir}")
        return ()


# ==============================
# 简化保存节点（UPDATED: 自动防覆盖 + 输出文件名）
# ==============================
class MIKKYSaveVideoSegmentsSimple:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "segments": ("IMAGE_LIST",),
                "filename_prefix": ("STRING", {"default": "segment"}),
                "fps": ("INT", {"default": 30, "min": 1, "max": 120}),
                "format": (["mp4", "gif"],),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filenames",)
    OUTPUT_NODE = True
    FUNCTION = "save_segments"
    CATEGORY = "MIKKY nodes/Video Segment"

    def tensor_to_numpy(self, img_tensor):
        img = img_tensor.cpu().numpy()
        return (img * 255).clip(0, 255).astype(np.uint8)

    def get_next_batch_number(self, directory, prefix):
        """
        扫描目录，查找符合 {prefix}_{batch}_... 格式的文件，
        返回下一个可用的 batch 编号。
        """
        batch_numbers = [0]
        # 正则匹配：以 prefix 开头，后面跟着 _数字_
        # re.escape 确保 prefix 中的特殊字符（如括号）被当作普通字符处理
        regex = re.compile(rf"^{re.escape(prefix)}_(\d{{4}})_")

        try:
            files = os.listdir(directory)
        except OSError:
            return 1

        for file_name in files:
            match = regex.match(file_name)
            if match:
                try:
                    batch_numbers.append(int(match.group(1)))
                except ValueError:
                    continue

        return max(batch_numbers) + 1

    def save_segments(self, segments: List[torch.Tensor], filename_prefix: str, fps: int, format: str):
        try:
            import imageio
        except ImportError:
            raise RuntimeError("imageio is required for SaveVideoSegmentsSimple. Run: pip install imageio[ffmpeg]")

        output_dir = folder_paths.get_output_directory()
        seg_dir = os.path.join(output_dir, "video_segments")
        os.makedirs(seg_dir, exist_ok=True)

        # 1. 获取当前批次号（防止覆盖）
        batch_counter = self.get_next_batch_number(seg_dir, filename_prefix)

        output_files = []

        for idx, segment in enumerate(segments):
            if segment.shape[0] == 0:
                continue

            frames = [self.tensor_to_numpy(frame) for frame in segment]

            # 2. 构建唯一文件名：前缀_批次(0001)_段号(0000).格式
            filename = f"{filename_prefix}_{batch_counter:04d}_{idx:04d}.{format}"
            filepath = os.path.join(seg_dir, filename)

            if format == "mp4":
                # quality=8 (macroblock-based), lower is better quality roughly, depends on ffmpeg version within imageio
                writer = imageio.get_writer(filepath, fps=fps, codec='libx264', quality=8, format='FFMPEG')
                for frame in frames:
                    writer.append_data(frame)
                writer.close()
            elif format == "gif":
                imageio.mimsave(filepath, frames, fps=fps, loop=0)

            print(f"[SaveVideoSegmentsSimple] Saved: {filepath}")
            output_files.append(filepath)

        print(f"[SaveVideoSegmentsSimple] ✅ Batch {batch_counter:04d} saved {len(output_files)} segments to: {seg_dir}")
        return (output_files,)


# ==============================
# 工具节点
# ==============================
class MIKKYImageListGetItem:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_list": ("IMAGE_LIST",),
                "index": ("INT", {"default": 0, "min": 0, "max": 9999}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "get_item"
    CATEGORY = "MIKKY nodes/Video Segment"

    def get_item(self, image_list: List[torch.Tensor], index: int) -> Tuple[torch.Tensor]:
        if index >= len(image_list):
            raise IndexError(f"Index {index} out of range (list has {len(image_list)} items)")
        return (image_list[index],)


class MIKKYImageListLength:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_list": ("IMAGE_LIST",),
            },
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "get_length"
    CATEGORY = "MIKKY nodes/Video Segment"

    def get_length(self, image_list: List[torch.Tensor]) -> Tuple[int]:
        return (len(image_list),)


# ==============================
# 注册所有节点
# ==============================
NODE_CLASS_MAPPINGS = {
    "MIKKYVideoSegmentByKeyframesDynamic": MIKKYVideoSegmentByKeyframesDynamic,
    "MIKKYSaveVideoSegments": MIKKYSaveVideoSegments,
    "MIKKYSaveVideoSegmentsSimple": MIKKYSaveVideoSegmentsSimple,
    "MIKKYImageListGetItem": MIKKYImageListGetItem,
    "MIKKYImageListLength": MIKKYImageListLength,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYVideoSegmentByKeyframesDynamic": "MIKKY SplitOptions: Segment Video (Dynamic)",
    "MIKKYSaveVideoSegments": "MIKKY SplitOptions: Save Segments (VHS)",
    "MIKKYSaveVideoSegmentsSimple": "MIKKY SplitOptions: Save Segments (Simple)",
    "MIKKYImageListGetItem": "MIKKY SplitOptions: Get Segment by Index",
    "MIKKYImageListLength": "MIKKY SplitOptions: Segment Count",
}

