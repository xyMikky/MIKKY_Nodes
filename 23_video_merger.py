"""
MIKKY Video Merger - 视频合并节点
用于合并多个帧率不一致的视频文件
"""
import os
import subprocess
import folder_paths
from typing import List, Tuple
import re
import json
import shutil


class MIKKYVideoMerger:
    """合并多个视频文件，自动处理不同帧率"""
    
    def __init__(self):
        self.ffmpeg_path = "ffmpeg"
        self.ffprobe_path = "ffprobe"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_files": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "视频文件路径列表（可以是字符串或从其他节点传入 LIST）",
                    "forceInput": False
                }),
                "output_filename": ("STRING", {
                    "default": "merged_video",
                    "tooltip": "输出文件名（不含扩展名）"
                }),
                "target_fps": ("INT", {
                    "default": 30,
                    "min": 1,
                    "max": 120,
                    "tooltip": "目标帧率（将所有视频转换到此帧率）"
                }),
                "merge_method": (["concat_copy", "concat_demuxer", "concat_filter", "re-encode"],{
                    "default": "concat_copy",
                    "tooltip": "concat_copy: 直接拼接+时间戳修复（推荐，避免静止帧）; concat_demuxer: 快速拼接; concat_filter: 需要参数相同; re-encode: 慢但兼容性好"
                }),
                "output_format": (["mp4", "avi", "mov", "mkv"],{
                    "default": "mp4"
                }),
                "video_codec": (["libx264", "libx265", "copy"],{
                    "default": "libx264",
                    "tooltip": "视频编码器（copy仅适用于concat方法）"
                }),
                "crf": ("INT", {
                    "default": 18,
                    "min": 0,
                    "max": 51,
                    "tooltip": "视频质量（0-51，越小质量越好，建议18-23）"
                }),
                "audio_codec": (["aac", "mp3", "copy"],{
                    "default": "aac",
                    "tooltip": "音频编码器"
                }),
                "preserve_original_fps": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "保持原始帧率：True=保持每个视频的原始帧率（避免音画不同步），False=统一转换到target_fps"
                }),
                "fix_timestamps": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "修复时间戳：True=重新生成时间戳（避免静止帧），False=保持原始时间戳"
                }),
            },
            "optional": {
                "video_files_list": ("LIST", {
                    "tooltip": "视频文件路径列表（从其他节点传入，优先级高于 video_files 字符串输入）"
                }),
                "video_folder": ("STRING", {
                    "default": "",
                    "tooltip": "视频文件夹路径（如果提供，将合并文件夹内所有视频）"
                }),
                "file_pattern": ("STRING", {
                    "default": "*.mp4",
                    "tooltip": "文件匹配模式（例如: *.mp4, segment_*.mp4）"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    FUNCTION = "merge_videos"
    CATEGORY = "MIKKY nodes/Video Utils"
    OUTPUT_NODE = True
    DESCRIPTION = "Merge multiple video files with different frame rates into one video."

    def check_ffmpeg(self):
        """检查ffmpeg是否可用"""
        # 首先尝试系统 ffmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"[MIKKYVideoMerger] 使用系统 ffmpeg")
                return True
        except Exception as e:
            print(f"[MIKKYVideoMerger] 系统 ffmpeg 未找到: {e}")
        
        # 尝试使用 imageio-ffmpeg 提供的 ffmpeg
        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"[MIKKYVideoMerger] 使用 imageio-ffmpeg: {ffmpeg_path}")
                # 将 ffmpeg 路径存储为实例变量
                self.ffmpeg_path = ffmpeg_path
                # 尝试查找 ffprobe（通常在同一目录）
                ffmpeg_dir = os.path.dirname(ffmpeg_path)
                ffmpeg_name = os.path.basename(ffmpeg_path)
                ffprobe_name = ffmpeg_name.replace("ffmpeg", "ffprobe")
                potential_ffprobe = os.path.join(ffmpeg_dir, ffprobe_name)
                
                # 检查 ffprobe 是否存在
                if os.path.exists(potential_ffprobe):
                    self.ffprobe_path = potential_ffprobe
                    print(f"[MIKKYVideoMerger] 找到 ffprobe: {potential_ffprobe}")
                else:
                    # imageio-ffmpeg 通常不包含 ffprobe，这是正常的
                    # 我们将使用 OpenCV 或 imageio 作为备选
                    print(f"[MIKKYVideoMerger] 注意: imageio-ffmpeg 不包含 ffprobe，将使用 OpenCV/imageio 获取视频信息")
                    self.ffprobe_path = "ffprobe"  # 标记为不可用
                
                return True
        except Exception as e:
            print(f"[MIKKYVideoMerger] imageio-ffmpeg 检查失败: {e}")
        
        return False

    def get_video_info(self, video_path: str) -> dict:
        """获取视频信息（帧率、分辨率等）"""
        # 方法1：尝试使用 ffprobe（如果可用）
        if self.ffprobe_path != "ffprobe":  # 有实际路径
            try:
                cmd = [
                    self.ffprobe_path,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_streams",
                    "-show_format",
                    video_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    video_stream = None
                    for stream in data.get("streams", []):
                        if stream.get("codec_type") == "video":
                            video_stream = stream
                            break
                    
                    if video_stream:
                        # 计算帧率
                        fps_str = video_stream.get("r_frame_rate", "30/1")
                        if "/" in fps_str:
                            num, den = fps_str.split("/")
                            fps = float(num) / float(den)
                        else:
                            fps = float(fps_str)
                        
                        return {
                            "fps": fps,
                            "width": video_stream.get("width", 0),
                            "height": video_stream.get("height", 0),
                            "duration": float(data.get("format", {}).get("duration", 0)),
                            "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))
                        }
            except Exception as e:
                print(f"[MIKKYVideoMerger] ffprobe 失败，尝试备选方案: {e}")
        
        # 方法2：使用 OpenCV 作为备选（ffprobe 不可用时）
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frame_count / fps if fps > 0 else 0
                cap.release()
                
                # 简单检测是否有音频（OpenCV 无法准确检测，默认假设有）
                has_audio = True  # 保守假设
                
                print(f"[MIKKYVideoMerger] 使用 OpenCV 获取视频信息: {os.path.basename(video_path)}")
                return {
                    "fps": fps,
                    "width": width,
                    "height": height,
                    "duration": duration,
                    "has_audio": has_audio
                }
        except Exception as e:
            print(f"[MIKKYVideoMerger] OpenCV 失败: {e}")
        
        # 方法3：使用 imageio 作为最后备选
        try:
            import imageio
            reader = imageio.get_reader(video_path)
            meta = reader.get_meta_data()
            
            fps = meta.get('fps', 30)
            size = meta.get('size', (1920, 1080))
            width, height = size
            duration = meta.get('duration', 0)
            has_audio = True  # imageio 无法准确检测，假设有
            
            reader.close()
            
            print(f"[MIKKYVideoMerger] 使用 imageio 获取视频信息: {os.path.basename(video_path)}")
            return {
                "fps": fps,
                "width": width,
                "height": height,
                "duration": duration,
                "has_audio": has_audio
            }
        except Exception as e:
            print(f"[MIKKYVideoMerger] imageio 失败: {e}")
        
        print(f"[MIKKYVideoMerger] ❌ 无法获取视频信息: {video_path}")
        return None

    def parse_video_files(self, video_files, video_folder: str = "", file_pattern: str = "*.mp4") -> List[str]:
        """解析视频文件列表（支持 str 或 list 输入）"""
        file_list = []
        
        # 如果提供了文件夹路径，扫描文件夹
        if video_folder and video_folder.strip():
            folder_path = video_folder.strip()
            if not os.path.isabs(folder_path):
                # 如果是相对路径，尝试相对于输出目录
                base_output_dir = folder_paths.get_output_directory()
                folder_path = os.path.join(base_output_dir, folder_path)
            
            if os.path.isdir(folder_path):
                print(f"[MIKKYVideoMerger] 扫描文件夹: {folder_path}")
                import glob
                pattern_path = os.path.join(folder_path, file_pattern)
                matched_files = glob.glob(pattern_path)
                file_list.extend(sorted(matched_files))
                print(f"[MIKKYVideoMerger] 找到 {len(matched_files)} 个匹配文件")
        
        # 处理 video_files 输入（支持 list 或 str）
        if video_files:
            # 情况1：如果是 list，直接处理
            if isinstance(video_files, list):
                print(f"[MIKKYVideoMerger] 接收到 list 格式输入，包含 {len(video_files)} 个文件")
                for file_path in video_files:
                    # 确保是字符串
                    if not isinstance(file_path, str):
                        file_path = str(file_path)
                    
                    file_path = file_path.strip()
                    if not file_path:
                        continue
                    
                    # 处理路径
                    if not os.path.isabs(file_path):
                        # 尝试多个可能的基础路径
                        possible_bases = [
                            folder_paths.get_output_directory(),
                            os.path.join(folder_paths.get_output_directory(), "video_segments"),
                            os.getcwd(),
                        ]
                        
                        found = False
                        for base in possible_bases:
                            test_path = os.path.join(base, file_path)
                            if os.path.exists(test_path):
                                file_path = test_path
                                found = True
                                break
                        
                        if not found:
                            print(f"[MIKKYVideoMerger] 警告: 找不到文件 {file_path}")
                            continue
                    
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        file_list.append(file_path)
                    else:
                        print(f"[MIKKYVideoMerger] 警告: 文件不存在 {file_path}")
            
            # 情况2：如果是字符串，按原来的方式处理
            elif isinstance(video_files, str) and video_files.strip():
                print(f"[MIKKYVideoMerger] 接收到字符串格式输入")
                # 支持换行符或逗号分隔
                lines = video_files.replace(",", "\n").split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 处理路径
                    if not os.path.isabs(line):
                        # 尝试多个可能的基础路径
                        possible_bases = [
                            folder_paths.get_output_directory(),
                            os.path.join(folder_paths.get_output_directory(), "video_segments"),
                            os.getcwd(),
                        ]
                        
                        found = False
                        for base in possible_bases:
                            test_path = os.path.join(base, line)
                            if os.path.exists(test_path):
                                line = test_path
                                found = True
                                break
                        
                        if not found:
                            print(f"[MIKKYVideoMerger] 警告: 找不到文件 {line}")
                            continue
                    
                    if os.path.exists(line) and os.path.isfile(line):
                        file_list.append(line)
                    else:
                        print(f"[MIKKYVideoMerger] 警告: 文件不存在 {line}")
        
        # 去重并排序
        file_list = sorted(list(set(file_list)))
        return file_list

    def merge_videos_concat_copy(self, video_files: List[str], output_path: str) -> bool:
        """使用逐个复制方式合并（最可靠，避免静止帧）"""
        try:
            print(f"[MIKKYVideoMerger] 使用 concat copy 方法（逐个视频拼接）...")
            
            # 方法：逐个提取视频和音频，然后拼接
            # 这样可以完全避免时间戳问题
            
            # 临时文件列表
            temp_dir = os.path.join(os.path.dirname(output_path), "temp_concat")
            os.makedirs(temp_dir, exist_ok=True)
            
            video_streams = []
            
            # 第一步：提取每个视频的流并重新封装（修复时间戳）
            print(f"[MIKKYVideoMerger] 步骤1: 重新封装每个视频...")
            for i, video in enumerate(video_files):
                print(f"[MIKKYVideoMerger]   处理 {i+1}/{len(video_files)}: {os.path.basename(video)}")
                
                # 获取视频信息
                video_info = self.get_video_info(video)
                if not video_info:
                    print(f"[MIKKYVideoMerger]   ⚠️ 无法获取视频信息，跳过")
                    continue
                
                # 重新封装视频，修复时间戳
                temp_video = os.path.join(temp_dir, f"video_{i:04d}.ts")  # 使用 TS 格式
                
                # 检查视频编码格式
                has_audio = self.check_video_has_audio(video)
                
                # 更robust的转换命令
                cmd = [
                    self.ffmpeg_path,
                    "-i", video,
                    "-map", "0:v:0",  # 映射第一个视频流
                ]
                
                if has_audio:
                    cmd.extend(["-map", "0:a:0"])  # 映射第一个音频流（如果有）
                
                cmd.extend([
                    "-c:v", "copy",  # 视频不重新编码
                    "-c:a", "copy",  # 音频不重新编码
                    "-bsf:v", "h264_mp4toannexb",  # 转换为 Annex B 格式
                    "-f", "mpegts",  # 使用 MPEG-TS 格式
                    "-muxdelay", "0",  # 禁用 mux 延迟
                    "-muxpreload", "0",  # 禁用预加载
                    "-y",
                    temp_video
                ])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    # 验证生成的 TS 文件
                    if os.path.exists(temp_video) and os.path.getsize(temp_video) > 0:
                        video_streams.append(temp_video)
                        print(f"[MIKKYVideoMerger]   ✓ 成功（大小: {os.path.getsize(temp_video) / 1024:.1f} KB）")
                    else:
                        print(f"[MIKKYVideoMerger]   ❌ 生成的文件为空")
                        raise Exception(f"生成的 TS 文件为空: {video}")
                else:
                    print(f"[MIKKYVideoMerger]   ⚠️ h264_mp4toannexb 失败，尝试不使用 bsf")
                    # 尝试不使用 bsf（某些编码格式不需要）
                    cmd_simple = [
                        self.ffmpeg_path,
                        "-i", video,
                        "-c", "copy",
                        "-f", "mpegts",
                        "-muxdelay", "0",
                        "-muxpreload", "0",
                        "-y",
                        temp_video
                    ]
                    result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=60)
                    if result.returncode == 0 and os.path.exists(temp_video) and os.path.getsize(temp_video) > 0:
                        video_streams.append(temp_video)
                        print(f"[MIKKYVideoMerger]   ✓ 成功（简化方式）")
                    else:
                        print(f"[MIKKYVideoMerger]   ❌ 处理失败: {result.stderr[:200]}")
                        raise Exception(f"无法处理视频: {video}")
            
            if not video_streams:
                raise Exception("没有成功处理任何视频")
            
            print(f"[MIKKYVideoMerger] 成功处理 {len(video_streams)} 个视频片段")
            
            # 第二步：使用 concat protocol 拼接（MPEG-TS 可以直接拼接）
            print(f"[MIKKYVideoMerger] 步骤2: 拼接所有视频流...")
            
            # 创建拼接列表文件（更可靠）
            concat_list = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for ts_file in video_streams:
                    # 使用相对路径或绝对路径
                    abs_path = os.path.abspath(ts_file)
                    escaped_path = abs_path.replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            print(f"[MIKKYVideoMerger] 拼接列表:")
            for i, ts_file in enumerate(video_streams, 1):
                print(f"[MIKKYVideoMerger]   {i}. {os.path.basename(ts_file)}")
            
            # 使用 concat demuxer（对于 TS 文件更可靠）
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
                "-c", "copy",  # 直接复制
                "-bsf:a", "aac_adtstoasc",  # 修复 AAC 音频（从 ADTS 转为 ASC）
                "-y",
                output_path
            ]
            
            print(f"[MIKKYVideoMerger] 执行最终拼接...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # 清理临时文件
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    print(f"[MIKKYVideoMerger] 清理临时文件")
            except Exception as e:
                print(f"[MIKKYVideoMerger] 清理临时文件失败: {e}")
            
            if result.returncode == 0:
                # 验证输出文件
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    print(f"[MIKKYVideoMerger] ✓ 合并成功！输出: {os.path.basename(output_path)}")
                    print(f"[MIKKYVideoMerger]   文件大小: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
                    return True
                else:
                    print(f"[MIKKYVideoMerger] ❌ 输出文件为空或不存在")
                    return False
            else:
                print(f"[MIKKYVideoMerger] concat copy 失败:")
                print(f"[MIKKYVideoMerger] {result.stderr[:500]}")
                return False
                
        except Exception as e:
            print(f"[MIKKYVideoMerger] concat copy 方法出错: {e}")
            # 清理临时文件
            try:
                temp_dir = os.path.join(os.path.dirname(output_path), "temp_concat")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except:
                pass
            return False

    def merge_videos_concat_demuxer(self, video_files: List[str], output_path: str, fix_timestamps: bool = True) -> bool:
        """使用concat demuxer直接拼接（推荐，类似PR，音画同步好）"""
        try:
            # 如果启用时间戳修复，先使用 ffmpeg 重新封装每个视频以修复时间戳
            if fix_timestamps:
                print(f"[MIKKYVideoMerger] 预处理视频，修复时间戳...")
                fixed_files = []
                temp_dir = os.path.join(os.path.dirname(output_path), "temp_fixed")
                os.makedirs(temp_dir, exist_ok=True)
                
                for i, video in enumerate(video_files):
                    temp_file = os.path.join(temp_dir, f"fixed_{i}.mp4")
                    
                    # 使用 ffmpeg 重新封装，修复时间戳
                    fix_cmd = [
                        self.ffmpeg_path,
                        "-i", video,
                        "-c", "copy",  # 不重新编码
                        "-fflags", "+genpts",  # 重新生成 PTS
                        "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                        "-map", "0",  # 复制所有流
                        "-y",
                        temp_file
                    ]
                    
                    print(f"[MIKKYVideoMerger]   处理 {i+1}/{len(video_files)}: {os.path.basename(video)}")
                    result = subprocess.run(fix_cmd, capture_output=True, text=True, timeout=60)
                    
                    if result.returncode == 0:
                        fixed_files.append(temp_file)
                    else:
                        print(f"[MIKKYVideoMerger]   警告: 预处理失败，使用原始文件")
                        fixed_files.append(video)
                
                # 使用修复后的文件
                video_files = fixed_files
            
            # 创建临时文件列表
            concat_file = output_path + ".concat.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for video in video_files:
                    # 转换为绝对路径并转义
                    abs_path = os.path.abspath(video)
                    # 使用正斜杠，FFmpeg 在 Windows 上也支持
                    abs_path = abs_path.replace("\\", "/")
                    f.write(f"file '{abs_path}'\n")
            
            # 执行ffmpeg合并 - 使用 copy 模式直接拼接，不重新编码
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",  # 直接复制，不重新编码
                "-y",
                output_path
            ]
            
            print(f"[MIKKYVideoMerger] 合并预处理后的视频...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # 清理临时文件
            try:
                os.remove(concat_file)
            except:
                pass
            
            # 清理预处理的临时文件
            if fix_timestamps:
                try:
                    import shutil
                    temp_dir = os.path.join(os.path.dirname(output_path), "temp_fixed")
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        print(f"[MIKKYVideoMerger] 清理临时文件")
                except Exception as e:
                    print(f"[MIKKYVideoMerger] 清理临时文件失败: {e}")
            
            if result.returncode == 0:
                return True
            else:
                print(f"[MIKKYVideoMerger] concat demuxer 失败: {result.stderr}")
                print(f"[MIKKYVideoMerger] 提示: 如果失败，请确保所有视频的编码格式相同")
                print(f"[MIKKYVideoMerger] 或尝试使用 're-encode' 方法")
                return False
                
        except Exception as e:
            print(f"[MIKKYVideoMerger] concat demuxer 方法出错: {e}")
            # 尝试清理临时文件
            if fix_timestamps:
                try:
                    import shutil
                    temp_dir = os.path.join(os.path.dirname(output_path), "temp_fixed")
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                except:
                    pass
            return False

    def merge_videos_concat_filter(self, video_files: List[str], output_path: str, video_codec: str, audio_codec: str) -> bool:
        """使用concat filter快速合并（要求视频参数相同）"""
        try:
            # 创建临时文件列表
            concat_file = output_path + ".concat.txt"
            with open(concat_file, "w", encoding="utf-8") as f:
                for video in video_files:
                    # 转换为绝对路径并转义
                    abs_path = os.path.abspath(video)
                    # ffmpeg concat需要转义单引号和特殊字符
                    escaped_path = abs_path.replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            # 执行ffmpeg合并
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c:v", video_codec,
                "-c:a", audio_codec,
                "-y",
                output_path
            ]
            
            print(f"[MIKKYVideoMerger] 执行命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # 清理临时文件
            try:
                os.remove(concat_file)
            except:
                pass
            
            if result.returncode == 0:
                return True
            else:
                print(f"[MIKKYVideoMerger] concat filter 失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[MIKKYVideoMerger] concat filter 方法出错: {e}")
            return False

    def check_video_has_audio(self, video_path: str) -> bool:
        """使用 FFmpeg 准确检测视频是否有音频流"""
        try:
            # 使用 ffprobe 风格的命令来检测音频流
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-hide_banner",
                "-f", "null",
                "-"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            # FFmpeg 信息在 stderr 中
            output = result.stderr
            
            # 查找音频流标识（更精确的匹配）
            lines = output.split('\n')
            for line in lines:
                # 查找 "Stream #X:Y" 格式的音频流
                if "Stream #" in line and "Audio:" in line:
                    # 确认是音频流（不是视频流）
                    if "Video:" not in line:
                        return True
            return False
        except Exception as e:
            print(f"[MIKKYVideoMerger] 检测音频流失败 {video_path}: {e}")
            # 如果检测失败，使用 OpenCV 作为备选
            try:
                import cv2
                cap = cv2.VideoCapture(video_path)
                # OpenCV 无法直接检测音频，但可以检查是否有多个流
                # 这里保守假设有音频
                cap.release()
                return True  # 保守假设有音频
            except:
                # 最后备选：假设有音频（避免错误）
                return True

    def merge_videos_reencode(
        self, 
        video_files: List[str], 
        output_path: str, 
        target_fps: int,
        video_codec: str,
        audio_codec: str,
        crf: int,
        preserve_original_fps: bool = True
    ) -> bool:
        """重新编码并合并（兼容性最好，处理不同帧率）"""
        try:
            # 获取所有视频的信息
            video_infos = []
            for video in video_files:
                info = self.get_video_info(video)
                if not info:
                    print(f"[MIKKYVideoMerger] 无法获取视频信息: {os.path.basename(video)}")
                    return False
                video_infos.append(info)
            
            # 获取第一个视频的分辨率作为目标分辨率
            first_info = video_infos[0]
            target_width = first_info["width"]
            target_height = first_info["height"]
            
            # 检测每个视频是否有音频流（使用 FFmpeg 准确检测）
            video_has_audio = []
            for video in video_files:
                has_audio = self.check_video_has_audio(video)
                video_has_audio.append(has_audio)
                print(f"[MIKKYVideoMerger] {os.path.basename(video)} - 音频: {'有' if has_audio else '无'}")
            
            # 构建ffmpeg filter_complex
            inputs = []
            filter_parts = []
            
            for i, (video, info) in enumerate(zip(video_files, video_infos)):
                inputs.extend(["-i", video])
                
                # 根据 preserve_original_fps 决定是否转换帧率
                if preserve_original_fps:
                    # 保持原始帧率，不强制转换
                    original_fps = info.get("fps", target_fps)
                    print(f"[MIKKYVideoMerger] 视频 {i+1} 保持原始帧率: {original_fps:.2f} fps")
                    # 只缩放和填充，不改变帧率
                    filter_parts.append(
                        f"[{i}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
                    )
                else:
                    # 强制转换到 target_fps
                    print(f"[MIKKYVideoMerger] 视频 {i+1} 转换帧率: {info.get('fps', target_fps):.2f} → {target_fps} fps")
                    filter_parts.append(
                        f"[{i}:v]fps={target_fps},scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
                    )
            
            # 合并所有视频流
            video_concat = "".join(f"[v{i}]" for i in range(len(video_files)))
            filter_parts.append(f"{video_concat}concat=n={len(video_files)}:v=1:a=0[outv]")
            
            filter_complex = ";".join(filter_parts)
            
            # 处理音频：只处理真正有音频的视频
            audio_inputs = []
            audio_indices = []  # 记录哪些输入有音频
            for i, has_audio in enumerate(video_has_audio):
                if has_audio:
                    audio_inputs.append(f"[{i}:a]")
                    audio_indices.append(i)
            
            # 构建完整命令
            cmd = [self.ffmpeg_path] + inputs
            
            # 如果有音频，添加音频处理
            if audio_inputs and len(audio_inputs) > 0:
                # 如果所有视频都有音频，直接合并
                if len(audio_inputs) == len(video_files):
                    audio_filter = "".join(audio_inputs) + f"concat=n={len(audio_inputs)}:v=0:a=1[outa]"
                    filter_complex_with_audio = filter_complex + ";" + audio_filter
                    cmd.extend([
                        "-filter_complex", filter_complex_with_audio,
                        "-map", "[outv]",
                        "-map", "[outa]",
                        "-c:a", audio_codec,
                    ])
                    print(f"[MIKKYVideoMerger] 所有视频都有音频，合并音频流")
                else:
                    # 部分视频有音频：只合并有音频的视频的音频流
                    print(f"[MIKKYVideoMerger] 部分视频有音频 ({len(audio_inputs)}/{len(video_files)})，只合并有音频的视频")
                    audio_filter = "".join(audio_inputs) + f"concat=n={len(audio_inputs)}:v=0:a=1[outa]"
                    filter_complex_with_audio = filter_complex + ";" + audio_filter
                    cmd.extend([
                        "-filter_complex", filter_complex_with_audio,
                        "-map", "[outv]",
                        "-map", "[outa]",
                        "-c:a", audio_codec,
                    ])
            else:
                # 没有音频，只处理视频
                print(f"[MIKKYVideoMerger] 所有视频都没有音频，只合并视频")
                cmd.extend([
                    "-filter_complex", filter_complex,
                    "-map", "[outv]",
                ])
            
            # 添加视频编码参数
            cmd.extend([
                "-c:v", video_codec,
                "-crf", str(crf),
                "-preset", "medium",
                "-y",
                output_path
            ])
            
            print(f"[MIKKYVideoMerger] 执行重编码合并...")
            if preserve_original_fps:
                fps_list = [f"{info.get('fps', target_fps):.2f}" for info in video_infos]
                print(f"[MIKKYVideoMerger] 目标: {target_width}x{target_height} @ 保持原始帧率 ({', '.join(fps_list)} fps)")
            else:
                print(f"[MIKKYVideoMerger] 目标: {target_width}x{target_height} @ {target_fps}fps")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                return True
            else:
                print(f"[MIKKYVideoMerger] 重编码失败: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"[MIKKYVideoMerger] 重编码方法出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def merge_videos(
        self,
        video_files,  # 字符串输入
        output_filename: str,
        target_fps: int,
        merge_method: str,
        output_format: str,
        video_codec: str,
        crf: int,
        audio_codec: str,
        preserve_original_fps: bool = True,
        fix_timestamps: bool = True,
        video_files_list: List[str] = None,  # LIST 输入（优先级高）
        video_folder: str = "",
        file_pattern: str = "*.mp4"
    ) -> Tuple[str]:
        """合并视频主函数（支持 str 或 list 格式的 video_files）"""
        
        # 检查ffmpeg
        if not self.check_ffmpeg():
            error_msg = "[MIKKYVideoMerger] ❌ 未找到ffmpeg，请安装ffmpeg并添加到PATH"
            print(error_msg)
            return (error_msg,)
        
        # 优先使用 video_files_list（从其他节点传入的 LIST）
        if video_files_list is not None and len(video_files_list) > 0:
            print(f"[MIKKYVideoMerger] 使用从其他节点传入的 LIST（{len(video_files_list)} 个文件）")
            # 直接使用 list，但仍需要调用 parse_video_files 来处理路径
            file_list = self.parse_video_files(video_files_list, video_folder, file_pattern)
        else:
            # 解析视频文件列表（字符串输入或文件夹扫描）
            file_list = self.parse_video_files(video_files, video_folder, file_pattern)
        
        if len(file_list) == 0:
            error_msg = "[MIKKYVideoMerger] ❌ 没有找到任何视频文件"
            print(error_msg)
            return (error_msg,)
        
        print(f"[MIKKYVideoMerger] 准备合并 {len(file_list)} 个视频:")
        for i, f in enumerate(file_list, 1):
            info = self.get_video_info(f)
            if info:
                print(f"  {i}. {os.path.basename(f)} - {info['width']}x{info['height']} @ {info['fps']:.2f}fps")
            else:
                print(f"  {i}. {os.path.basename(f)}")
        
        # 准备输出路径
        output_dir = folder_paths.get_output_directory()
        merged_dir = os.path.join(output_dir, "merged_videos")
        os.makedirs(merged_dir, exist_ok=True)
        
        output_path = os.path.join(merged_dir, f"{output_filename}.{output_format}")
        
        # 如果文件存在，添加序号
        if os.path.exists(output_path):
            counter = 1
            while True:
                output_path = os.path.join(merged_dir, f"{output_filename}_{counter:04d}.{output_format}")
                if not os.path.exists(output_path):
                    break
                counter += 1
        
        # 根据方法选择合并策略
        success = False
        if merge_method == "concat_copy":
            print(f"[MIKKYVideoMerger] 使用 concat copy 方法（逐个拼接，避免静止帧）...")
            success = self.merge_videos_concat_copy(file_list, output_path)
        elif merge_method == "concat_demuxer":
            print(f"[MIKKYVideoMerger] 使用 concat demuxer 方法（直接拼接，类似 PR）...")
            if fix_timestamps:
                print(f"[MIKKYVideoMerger] 启用时间戳修复（避免静止帧问题）")
            success = self.merge_videos_concat_demuxer(file_list, output_path, fix_timestamps)
        elif merge_method == "concat_filter":
            print(f"[MIKKYVideoMerger] 使用 concat filter 方法（快速）...")
            success = self.merge_videos_concat_filter(file_list, output_path, video_codec, audio_codec)
        else:  # re-encode
            fps_mode = "保持原始帧率" if preserve_original_fps else f"统一到 {target_fps} fps"
            print(f"[MIKKYVideoMerger] 使用重编码方法（兼容性好）...")
            print(f"[MIKKYVideoMerger] 帧率模式: {fps_mode}")
            success = self.merge_videos_reencode(
                file_list, output_path, target_fps, video_codec, audio_codec, crf, preserve_original_fps
            )
        
        if success and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            print(f"[MIKKYVideoMerger] ✅ 合并成功!")
            print(f"[MIKKYVideoMerger] 输出文件: {output_path}")
            print(f"[MIKKYVideoMerger] 文件大小: {file_size:.2f} MB")
            return (output_path,)
        else:
            error_msg = "[MIKKYVideoMerger] ❌ 合并失败，请查看日志"
            print(error_msg)
            return (error_msg,)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYVideoMerger": MIKKYVideoMerger
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYVideoMerger": "MIKKY Video Merger"
}
