"""
MIKKY Storyboard Extractor - 视频关键帧提取节点
用于从视频中自动提取关键帧（故事板）
"""
import torch
import cv2
import numpy as np
import math
from typing import List, Tuple


class MIKKYIntBatch:
    """从整数列表中获取指定索引的值
    
    支持输入：
    - STRING类型：逗号分隔的整数字符串（如 "0,30,78,120"），来自 ExtractStoryboards 的 indexes_string
    - INT类型：单个整数
    - LIST/TUPLE类型：整数列表或元组
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ints": ("STRING", {
                    "default": "0,1,2,3",
                    "tooltip": "整数列表，可以是逗号分隔的字符串（如 '0,30,78,120'）或单个整数"
                }),
                "int_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 9999,
                    "step": 1,
                    "tooltip": "要获取的整数在列表中的索引位置"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("int_value",)
    FUNCTION = "execute"
    CATEGORY = "MIKKY nodes/Storyboard"
    DESCRIPTION = "从整数列表中获取指定索引的值。支持逗号分隔的字符串输入（如 '0,30,78,120'）。"

    def execute(self, ints, int_index):
        # 解析输入为整数列表
        int_list = []
        
        if isinstance(ints, str):
            # 如果是字符串，解析逗号分隔的整数
            try:
                # 移除空格并分割
                parts = [p.strip() for p in ints.split(",") if p.strip()]
                int_list = [int(p) for p in parts]
            except (ValueError, AttributeError):
                print(f"[MIKKYIntBatch] Warning: Failed to parse string '{ints}' as integers. Returning 0.")
                return (0,)
        elif isinstance(ints, (list, tuple)):
            # 如果是列表或元组，直接使用
            int_list = [int(x) for x in ints if isinstance(x, (int, str))]
        elif isinstance(ints, int):
            # 如果是单个整数，转换为列表
            int_list = [ints]
        else:
            print(f"[MIKKYIntBatch] Warning: Unsupported input type {type(ints)}. Returning 0.")
            return (0,)
        
        # 检查索引范围
        if int_index < 0 or int_index >= len(int_list):
            print(f"[MIKKYIntBatch] Warning: Index {int_index} out of range for list of length {len(int_list)}. Returning 0.")
            return (0,)
        
        return (int_list[int_index],)


class MIKKYIntBatchSize:
    """获取整数集合的大小
    
    支持输入：
    - STRING类型：逗号分隔的整数字符串（如 "0,30,78,120"），来自 ExtractStoryboards 的 indexes_string
    - INT类型：单个整数
    - LIST/TUPLE类型：整数列表或元组
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ints": ("STRING", {
                    "default": "0,1,2,3",
                    "tooltip": "整数列表，可以是逗号分隔的字符串（如 '0,30,78,120'）或单个整数"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("ints_size",)
    FUNCTION = "execute"
    CATEGORY = "MIKKY nodes/Storyboard"
    DESCRIPTION = "获取整数列表的大小（长度）。支持逗号分隔的字符串输入（如 '0,30,78,120'）。"

    def execute(self, ints):
        # 解析输入为整数列表
        int_list = []
        
        if isinstance(ints, str):
            # 如果是字符串，解析逗号分隔的整数
            try:
                # 移除空格并分割
                parts = [p.strip() for p in ints.split(",") if p.strip()]
                int_list = [int(p) for p in parts]
            except (ValueError, AttributeError):
                print(f"[MIKKYIntBatchSize] Warning: Failed to parse string '{ints}' as integers. Returning 0.")
                return (0,)
        elif isinstance(ints, (list, tuple)):
            # 如果是列表或元组，直接使用
            int_list = [int(x) for x in ints if isinstance(x, (int, str))]
        elif isinstance(ints, int):
            # 如果是单个整数，返回1
            return (1,)
        else:
            print(f"[MIKKYIntBatchSize] Warning: Unsupported input type {type(ints)}. Returning 0.")
            return (0,)
        
        return (len(int_list),)


class MIKKYExtractStoryboards:
    """从视频中自动提取关键帧（故事板）"""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "threshold": ("FLOAT", {
                    "default": 0.1,
                    "min": -1.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "相似度阈值，值越小越敏感"
                }),
                "mergeInterFrames": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 999,
                    "step": 1,
                    "tooltip": "合并间隔帧数（每批最小帧数）"
                }),
                "maxFrames": ("INT", {
                    "default": 999999,
                    "min": 1,
                    "max": 999999999,
                    "step": 1,
                    "tooltip": "每批最大帧数（超过即拆分）"
                }),
                "audio_weight": ("FLOAT", {
                    "default": 0.3,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "音频分析权重（0=仅图像，1=仅音频，0.3=图像70%+音频30%）"
                }),
            },
            "optional": {
                "audio": ("AUDIO", {
                    "tooltip": "可选音频输入，用于结合音频特征进行分段"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("keyframes", "indexes_string")
    FUNCTION = "execute"
    CATEGORY = "MIKKY nodes/Storyboard"
    DESCRIPTION = "使用SSIM算法自动提取视频关键帧，支持结合音频分析，支持批量处理和帧数限制"

    def ssim(self, img1, img2, C1=0.01**2, C2=0.03**2):
        """
        计算两张图片的结构相似性指数（SSIM）
        参数:
            img1, img2: 输入的两张图片，shape为(H, W, C)或(H, W)
            C1, C2: 稳定常数
        返回:
            ssim: SSIM值，范围0~1，值越大越相似
        """
        # 转换为numpy数组
        if isinstance(img1, torch.Tensor):
            img1 = img1.cpu().numpy()
        if isinstance(img2, torch.Tensor):
            img2 = img2.cpu().numpy()

        # 如果是彩色图像，先转为灰度
        if img1.ndim == 3 and img1.shape[-1] == 3:
            img1 = 0.299 * img1[..., 0] + 0.587 * img1[..., 1] + 0.114 * img1[..., 2]
            img2 = 0.299 * img2[..., 0] + 0.587 * img2[..., 1] + 0.114 * img2[..., 2]

        # 确保是float32类型
        img1 = img1.astype(np.float32)
        img2 = img2.astype(np.float32)

        # 计算均值
        mu1 = img1.mean()
        mu2 = img2.mean()

        # 计算方差
        sigma1 = ((img1 - mu1) ** 2).mean()
        sigma2 = ((img2 - mu2) ** 2).mean()

        # 计算协方差
        sigma12 = ((img1 - mu1) * (img2 - mu2)).mean()

        # 计算SSIM
        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1 + sigma2 + C2)
        
        if denominator == 0:
            return 0.0
        
        ssim = numerator / denominator

        # 保证结果在0~1之间
        return max(0.0, min(1.0, float(ssim)))

    def mse(self, img1, img2):
        """
        计算两张图片的均方误差（MSE）
        参数:
            img1, img2: 输入的两张图片，shape相同
        返回:
            mse: 均方误差，值越小越相似
        """
        # 转换为numpy数组
        if isinstance(img1, torch.Tensor):
            img1 = img1.cpu().numpy()
        if isinstance(img2, torch.Tensor):
            img2 = img2.cpu().numpy()

        # 如果是彩色图像，先转为灰度
        if img1.ndim == 3 and img1.shape[-1] == 3:
            img1 = 0.299 * img1[..., 0] + 0.587 * img1[..., 1] + 0.114 * img1[..., 2]
            img2 = 0.299 * img2[..., 0] + 0.587 * img2[..., 1] + 0.114 * img2[..., 2]

        # 保证类型为float32
        img1 = img1.astype(np.float32)
        img2 = img2.astype(np.float32)

        # 计算MSE
        mse_val = np.mean((img1 - img2) ** 2)
        return float(mse_val)

    def extract_audio_features(self, audio, num_frames, fps=None):
        """
        从音频中提取特征，映射到视频帧
        参数:
            audio: ComfyUI音频格式 {'waveform': tensor, 'sample_rate': int}
            num_frames: 视频帧数
            fps: 视频帧率（如果提供，用于更精确的映射）
        返回:
            audio_features: 每帧对应的音频特征列表（能量变化率）
        """
        if audio is None:
            return None

        try:
            waveform = audio['waveform']
            sample_rate = audio['sample_rate']

            # 确保waveform是2D或3D
            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)
            if waveform.dim() == 2:
                # [Channels, Samples] -> [1, Channels, Samples]
                waveform = waveform.unsqueeze(0)
            
            # 取第一个batch和所有通道的平均值
            if waveform.dim() == 3:
                # [Batch, Channels, Samples] -> [Channels, Samples]
                waveform = waveform[0]
            
            # 如果是多声道，取平均值
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0)
            else:
                waveform = waveform[0]

            # 转换为numpy
            if isinstance(waveform, torch.Tensor):
                waveform = waveform.cpu().numpy()

            total_samples = len(waveform)
            
            # 计算每帧对应的采样点数
            if fps is not None and fps > 0:
                samples_per_frame = int(sample_rate / fps)
            else:
                # 如果没有fps，根据总采样数和帧数估算
                samples_per_frame = max(1, total_samples // num_frames)

            # 计算音频能量（RMS）的滑动窗口
            window_size = samples_per_frame
            hop_size = max(1, window_size // 4)  # 重叠窗口，提高精度

            # 计算每个窗口的RMS能量
            energies = []
            for i in range(0, total_samples - window_size + 1, hop_size):
                window = waveform[i:i + window_size]
                rms = np.sqrt(np.mean(window ** 2))
                energies.append(rms)

            # 如果能量列表为空，返回None
            if not energies:
                return None

            # 将能量映射到帧（确保返回num_frames-1个值，对应相邻帧之间的变化）
            num_energy_windows = len(energies)
            if num_energy_windows < 2:
                return None

            # 计算相邻能量窗口之间的变化率
            energy_changes = []
            for i in range(num_energy_windows - 1):
                if energies[i] > 0:
                    change = abs(energies[i + 1] - energies[i]) / (energies[i] + 1e-6)
                else:
                    change = abs(energies[i + 1] - energies[i])
                energy_changes.append(change)

            # 归一化到0-1范围
            if energy_changes:
                max_change = max(energy_changes) if max(energy_changes) > 0 else 1.0
                energy_changes = [c / max_change for c in energy_changes]
            else:
                return None

            # 将能量变化映射到视频帧对（num_frames-1个值）
            num_changes = len(energy_changes)
            audio_changes = []

            for frame_idx in range(num_frames - 1):
                # 计算该帧对对应的能量变化索引
                change_idx = int((frame_idx / (num_frames - 1)) * num_changes)
                change_idx = min(change_idx, num_changes - 1)
                
                if change_idx < len(energy_changes):
                    audio_changes.append(energy_changes[change_idx])
                else:
                    audio_changes.append(0.0)

            # 确保返回的列表长度正确
            if len(audio_changes) != num_frames - 1:
                # 如果长度不匹配，进行插值或截断
                if len(audio_changes) < num_frames - 1:
                    # 需要扩展：重复最后一个值
                    while len(audio_changes) < num_frames - 1:
                        audio_changes.append(audio_changes[-1] if audio_changes else 0.0)
                else:
                    # 需要截断
                    audio_changes = audio_changes[:num_frames - 1]

            return audio_changes

        except Exception as e:
            print(f"[MIKKY ExtractStoryboards] Error extracting audio features: {e}")
            import traceback
            traceback.print_exc()
            return None

    def execute(self, image, threshold, mergeInterFrames, maxFrames, audio_weight, audio=None):
        """
        执行关键帧提取（结合图像和音频分析）
        参数:
            image: 输入的视频帧序列，shape为[B, H, W, C]
            threshold: 相似度阈值
            mergeInterFrames: 合并间隔帧数
            maxFrames: 每批最大帧数
            audio_weight: 音频分析权重（0-1）
            audio: 可选的音频输入
        返回:
            keyframes: 提取的关键帧图像
            indexes_string: 关键帧索引的字符串（逗号分隔）
        """
        # image: [B, H, W, C]
        B = image.shape[0]
        
        if B <= 1:
            # 如果只有一帧或没有帧，返回第一帧
            keyframes = [0]
            keyframes_tensor = image[keyframes]
            indexes_str = ','.join(map(str, keyframes))
            return (keyframes_tensor, indexes_str)

        # 计算相邻帧之间的SSIM值
        ssim_list = []
        for i in range(B - 1):
            ssim_val = self.ssim(image[i], image[i + 1])
            ssim_list.append(ssim_val)

        # 提取音频特征（如果提供）
        audio_features = None
        if audio is not None and audio_weight > 0:
            audio_features = self.extract_audio_features(audio, B)
            if audio_features is not None:
                print(f"[MIKKY ExtractStoryboards] Audio features extracted: {len(audio_features)} values")
                print(f"[MIKKY ExtractStoryboards] Audio weight: {audio_weight:.2f}, Image weight: {1.0 - audio_weight:.2f}")
            else:
                print(f"[MIKKY ExtractStoryboards] Failed to extract audio features, using image only")
                audio_weight = 0.0

        if not ssim_list:
            keyframes = [0]
            keyframes_tensor = image[keyframes]
            indexes_str = ','.join(map(str, keyframes))
            return (keyframes_tensor, indexes_str)

        print(f"[MIKKY ExtractStoryboards] SSIM list length: {len(ssim_list)}")
        print(f"[MIKKY ExtractStoryboards] SSIM values: {ssim_list[:10]}..." if len(ssim_list) > 10 else f"[MIKKY ExtractStoryboards] SSIM values: {ssim_list}")

        # 计算SSIM的统计值
        ssim_max = max(ssim_list)
        ssim_mean = sum(ssim_list) / len(ssim_list)
        ssim_limit = ssim_max - (ssim_max - ssim_mean) * 2 - threshold
        
        print(f"[MIKKY ExtractStoryboards] SSIM max: {ssim_max:.4f}, mean: {ssim_mean:.4f}, limit: {ssim_limit:.4f}")

        # 结合音频特征计算综合得分
        if audio_features is not None and len(audio_features) == len(ssim_list):
            # 归一化SSIM：转换为差异度（1 - ssim），值越大表示差异越大
            ssim_diff = [1.0 - s for s in ssim_list]
            
            # 归一化音频特征：已经是0-1范围的变化率
            # 音频变化越大，越可能是分段点
            
            # 加权结合：图像差异度 + 音频变化率
            image_weight = 1.0 - audio_weight
            combined_scores = []
            for i in range(len(ssim_list)):
                combined_score = image_weight * ssim_diff[i] + audio_weight * audio_features[i]
                combined_scores.append(combined_score)
            
            # 计算综合得分的统计值
            score_max = max(combined_scores)
            score_mean = sum(combined_scores) / len(combined_scores)
            score_min = min(combined_scores)
            
            # 对于差异度得分，值越大表示差异越大，越可能是分段点
            # 使用相对阈值方法，确保阈值在合理范围内（0-1）
            # 使用：score_limit = mean + (max - mean) * factor
            # 为了与原始SSIM的threshold行为一致：
            # threshold越大 -> 应该检测更多分段点 -> score_limit应该越小 -> factor应该越小
            # threshold越小 -> 应该检测更少分段点 -> score_limit应该越大 -> factor应该越大
            # 映射：threshold 0.0 -> factor 0.8（严格），threshold 0.2 -> factor 0.3（宽松）
            factor = 0.8 - threshold * 2.5  # threshold在0-0.2范围内，factor在0.8-0.3
            factor = max(0.2, min(0.9, factor))  # 限制在合理范围
            score_limit = score_mean + (score_max - score_mean) * factor
            
            # 确保阈值不超过1.0，不低于mean
            score_limit = max(score_mean, min(1.0, score_limit))
            
            print(f"[MIKKY ExtractStoryboards] Combined scores - min: {score_min:.4f}, max: {score_max:.4f}, mean: {score_mean:.4f}, limit: {score_limit:.4f}")
            print(f"[MIKKY ExtractStoryboards] Using combined image+audio analysis (image: {image_weight:.2f}, audio: {audio_weight:.2f})")
            print(f"[MIKKY ExtractStoryboards] Combined scores sample: {combined_scores[:10] if len(combined_scores) > 10 else combined_scores}")
            
            # 找出所有高于阈值的关键帧（差异度大，说明变化明显）
            keyframes = [0]  # 第一帧总是关键帧
            for i, score in enumerate(combined_scores):
                if score > score_limit:
                    keyframes.append(i + 1)
            
            print(f"[MIKKY ExtractStoryboards] Initial keyframes (combined): {keyframes[:20] if len(keyframes) > 20 else keyframes}")
        else:
            # 仅使用图像SSIM
            print(f"[MIKKY ExtractStoryboards] Using image-only analysis (no audio or audio_weight=0)")
            keyframes = [0]  # 第一帧总是关键帧
            for i, ssim_val in enumerate(ssim_list):
                if ssim_val < ssim_limit:
                    keyframes.append(i + 1)

        print(f"[MIKKY ExtractStoryboards] Initial keyframes: {keyframes}")

        # 从前往后筛选，密集关键帧只保留最后一个
        filtered_keyframes = [keyframes[0]]
        for kf in keyframes[1:]:
            if kf - filtered_keyframes[-1] > mergeInterFrames:
                filtered_keyframes.append(kf)
            else:
                filtered_keyframes[-1] = kf  # 替换为更大的索引

        # 检查尾部：如果尾部到视频结尾的帧数 < mergeInterFrames，向左归并
        while len(filtered_keyframes) > 1 and (B - filtered_keyframes[-1]) < mergeInterFrames:
            filtered_keyframes.pop()

        print(f"[MIKKY ExtractStoryboards] Filtered keyframes: {filtered_keyframes}")

        # 如果间隔帧数超过最大帧数，则拆分成每批都小于或等于maxFrames的多个批
        split_points = [0]
        for i in range(1, len(filtered_keyframes) + 1):
            start = filtered_keyframes[i - 1]
            end = filtered_keyframes[i] if i < len(filtered_keyframes) else B
            num = end - start

            if num > maxFrames:
                # 需要拆分
                num_per = math.ceil(num / maxFrames)
                frames_per = num // num_per
                
                print(f"[MIKKY ExtractStoryboards] Splitting segment [{start}, {end}]: {num} frames into {num_per} batches of ~{frames_per} frames")
                
                for j in range(num_per):
                    if j < num_per - 1:
                        split_points.append(start + (j + 1) * frames_per)
                    else:
                        split_points.append(end)
            else:
                split_points.append(end)

        final_keyframes = sorted(set(split_points))  # 去重并排序

        # 如果最后一个是 B，则删除（避免越界）
        if final_keyframes and final_keyframes[-1] >= B:
            final_keyframes = [kf for kf in final_keyframes if kf < B]

        # 确保至少有一个关键帧
        if not final_keyframes:
            final_keyframes = [0]

        print(f"[MIKKY ExtractStoryboards] Final keyframes: {final_keyframes}")

        # 提取关键帧
        keyframes_tensor = image[final_keyframes]
        indexes_str = ','.join(map(str, final_keyframes))

        return (keyframes_tensor, indexes_str)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYExtractStoryboards": MIKKYExtractStoryboards,
    "MIKKYIntBatch": MIKKYIntBatch,
    "MIKKYIntBatchSize": MIKKYIntBatchSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYExtractStoryboards": "MIKKY Extract Storyboards",
    "MIKKYIntBatch": "MIKKY Int Batch",
    "MIKKYIntBatchSize": "MIKKY Int Batch Size",
}

