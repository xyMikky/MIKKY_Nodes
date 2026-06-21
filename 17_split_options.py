import torch
import os
import folder_paths
import torchaudio
from typing import List, Tuple, Dict


# ==============================
# 音频分割节点
# ==============================
class MIKKYAudioSegmentByKeyframes:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "keyframes": ("STRING", {"default": "0,30,78", "multiline": False}),
                "fps": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 120.0, "step": 0.01,
                                  "tooltip": "Must match the video FPS used for keyframes"}),
            },
        }

    RETURN_TYPES = ("AUDIO_LIST",)
    RETURN_NAMES = ("audio_segments",)
    FUNCTION = "segment_audio"
    CATEGORY = "MIKKY nodes/Audio Segment"

    def segment_audio(self, audio: Dict, keyframes: str, fps: float) -> Tuple[List[Dict]]:
        # 1. 获取音频基础信息
        waveform = audio['waveform']  # 通常形状为 [Batch, Channels, Samples] 或 [Channels, Samples]
        sample_rate = audio['sample_rate']

        # 确保 waveform 是 3D [Batch, Channels, Samples] 以便统一处理
        if waveform.dim() == 2:
            waveform = waveform.unsqueeze(0)

        total_samples = waveform.shape[-1]

        # 2. 解析关键帧
        try:
            kf_list = [int(x.strip()) for x in keyframes.split(",") if x.strip()]
            kf_list = sorted(set(kf_list))
        except Exception as e:
            raise ValueError(f"Invalid keyframes format: {e}")

        if not kf_list:
            raise ValueError("At least one keyframe must be provided.")
        if kf_list[0] != 0:
            raise ValueError("First keyframe must be 0.")

        # 3. 将帧索引转换为音频采样点索引
        # 公式: SampleIndex = (FrameIndex / FPS) * SampleRate
        boundaries_samples = []
        for frame_idx in kf_list:
            sample_idx = int((frame_idx / fps) * sample_rate)
            # 防止索引越界（虽然切片会自动处理，但为了逻辑严谨）
            sample_idx = min(sample_idx, total_samples)
            boundaries_samples.append(sample_idx)

        # 添加结束点
        if boundaries_samples[-1] < total_samples:
            boundaries_samples.append(total_samples)

        # 4. 执行切片
        segments = []
        for i in range(len(boundaries_samples) - 1):
            start = boundaries_samples[i]
            end = boundaries_samples[i + 1]

            if start < end:
                # 切片 [Batch, Channels, Start:End]
                new_wave = waveform[..., start:end]
                segments.append({"waveform": new_wave, "sample_rate": sample_rate})

        if not segments:
            raise ValueError("No valid audio segments generated. Check FPS or Audio length.")

        print(f"[AudioSegment] Split audio into {len(segments)} segments based on FPS {fps}.")
        return (segments,)


# ==============================
# 保存音频分段节点
# ==============================
class MIKKYSaveAudioSegments:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_segments": ("AUDIO_LIST",),
                "filename_prefix": ("STRING", {"default": "audio_seg"}),
                "save_output": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "save_segments"
    CATEGORY = "MIKKY nodes/Audio Segment"

    def save_segments(self, audio_segments: List[Dict], filename_prefix: str, save_output: bool):
        if not save_output:
            return ()

        output_dir = folder_paths.get_output_directory()
        seg_dir = os.path.join(output_dir, "audio_segments")
        os.makedirs(seg_dir, exist_ok=True)

        for idx, segment in enumerate(audio_segments):
            waveform = segment['waveform']
            sample_rate = segment['sample_rate']

            # torchaudio.save 期望 [Channels, Samples]，如果是由 Batch 维度 [1, C, N]，需要 squeeze
            if waveform.dim() == 3:
                waveform = waveform.squeeze(0)

            filename = f"{filename_prefix}_{idx:04d}.wav"
            filepath = os.path.join(seg_dir, filename)

            torchaudio.save(filepath, waveform, sample_rate)
            print(f"[SaveAudioSegments] Saved: {filepath}")

        return ()


# ==============================
# 工具节点：从列表中获取单个音频
# ==============================
class MIKKYAudioListGetItem:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_list": ("AUDIO_LIST",),
                "index": ("INT", {"default": 0, "min": 0, "max": 9999}),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "get_item"
    CATEGORY = "MIKKY nodes/Audio Segment"

    def get_item(self, audio_list: List[Dict], index: int) -> Tuple[Dict]:
        if index >= len(audio_list):
            print(f"[Warning] Index {index} out of range for audio list (len {len(audio_list)}). Returning last item.")
            return (audio_list[-1],)
        return (audio_list[index],)


# ==============================
# 注册节点
# ==============================
NODE_CLASS_MAPPINGS = {
    "MIKKYAudioSegmentByKeyframes": MIKKYAudioSegmentByKeyframes,
    "MIKKYSaveAudioSegments": MIKKYSaveAudioSegments,
    "MIKKYAudioListGetItem": MIKKYAudioListGetItem,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYAudioSegmentByKeyframes": "MIKKY SplitOptions: Segment Audio (Sync)",
    "MIKKYSaveAudioSegments": "MIKKY SplitOptions: Save Audio Segments",
    "MIKKYAudioListGetItem": "MIKKY SplitOptions: Get Audio Segment",
}

