"""
MIKKY Save Logs List - 保存日志列表节点
用于将字符串列表（如打标结果）保存为多个文本文件
"""
import os
from typing import List, Tuple
import folder_paths


class MIKKYSaveLogsList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "logs_list": ("LIST",),
                "save_dir": ("STRING", {
                    "default": "./outputs/logs",
                    "tooltip": "保存目录路径"
                }),
                "filename_prefix": ("STRING", {
                    "default": "ComfyUI",
                    "tooltip": "文件名前缀"
                }),
                "filename_separator": ("STRING", {
                    "default": "_",
                    "tooltip": "文件名分隔符"
                }),
                "filename_padding": ("INT", {
                    "default": 4,
                    "min": 1,
                    "max": 8,
                    "tooltip": "文件名数字填充位数"
                }),
                "file_extension": ("STRING", {
                    "default": ".txt",
                    "tooltip": "文件扩展名（包含点号）"
                }),
                "encoding": ("STRING", {
                    "default": "utf-8",
                    "tooltip": "文件编码格式"
                }),
                "filename_suffix": ("STRING", {
                    "default": "",
                    "tooltip": "文件名后缀（在编号之后）"
                }),
                "avoid_overwrite": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "避免覆盖：如果文件已存在，自动递增编号直到找到可用文件名"
                }),
            },
            "optional": {
                "image_filenames": ("STRING", {
                    "default": "",
                    "tooltip": "图像文件名列表（逗号分隔，不含扩展名）。如果提供，将使用这些文件名作为txt文件名，忽略其他命名参数"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_files",)
    FUNCTION = "save_all_logs"
    CATEGORY = "MIKKY nodes/File Utils"
    OUTPUT_NODE = True
    DESCRIPTION = "Save each element of a list (logs_list) into separate text files."

    def save_all_logs(
        self,
        logs_list: List[str],
        save_dir: str,
        filename_prefix: str,
        filename_separator: str,
        filename_padding: int,
        file_extension: str,
        encoding: str,
        filename_suffix: str,
        avoid_overwrite: bool,
        image_filenames: str = ""
    ) -> Tuple[str]:
        """将字符串列表保存为多个文件"""

        if not isinstance(logs_list, list) or len(logs_list) == 0:
            print("[MIKKYSaveLogsList] Warning: logs_list is empty or invalid.")
            return ("[MIKKYSaveLogsList] logs_list is empty or invalid.",)

        # 如果save_dir是相对路径，使用ComfyUI的输出目录
        if not os.path.isabs(save_dir):
            base_output_dir = folder_paths.get_output_directory()
            save_dir = os.path.join(base_output_dir, save_dir.lstrip("./"))

        # 创建目录
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            error_msg = f"[MIKKYSaveLogsList] Failed to create directory {save_dir}: {e}"
            print(error_msg)
            return (error_msg,)

        saved_paths = []
        
        # 解析图像文件名（如果提供）
        use_image_names = False
        image_name_list = []
        if image_filenames and image_filenames.strip():
            image_name_list = [name.strip() for name in image_filenames.split(",") if name.strip()]
            if len(image_name_list) > 0:
                use_image_names = True
                print(f"[MIKKYSaveLogsList] Using image filenames for output files: {len(image_name_list)} names provided")
                if len(image_name_list) != len(logs_list):
                    print(f"[MIKKYSaveLogsList] Warning: Image filenames count ({len(image_name_list)}) != logs_list count ({len(logs_list)})")
        
        # 如果避免覆盖，先查找目录中已有的最大编号（仅在不使用图像文件名时）
        start_index = 1
        if avoid_overwrite and not use_image_names:
            try:
                existing_files = [f for f in os.listdir(save_dir) if os.path.isfile(os.path.join(save_dir, f))]
                max_index = 0
                prefix_pattern = f"{filename_prefix}{filename_separator}"
                suffix_pattern = f"{filename_suffix}{file_extension}"
                
                for filename in existing_files:
                    if filename.startswith(prefix_pattern) and filename.endswith(suffix_pattern):
                        # 提取编号部分
                        middle_part = filename[len(prefix_pattern):-len(suffix_pattern)]
                        try:
                            # 尝试解析编号（可能包含其他字符，取数字部分）
                            import re
                            numbers = re.findall(r'\d+', middle_part)
                            if numbers:
                                file_index = int(numbers[0])
                                max_index = max(max_index, file_index)
                        except (ValueError, IndexError):
                            pass
                
                # 从最大编号+1开始
                start_index = max_index + 1
                if max_index > 0:
                    print(f"[MIKKYSaveLogsList] Found existing files, starting from index {start_index}")
            except Exception as e:
                print(f"[MIKKYSaveLogsList] Warning: Could not check existing files: {e}, starting from 1")

        for i, text in enumerate(logs_list):
            # 确保text是字符串
            if not isinstance(text, str):
                text = str(text)

            # 生成文件名
            if use_image_names:
                # 使用图像文件名
                if i < len(image_name_list):
                    base_filename = image_name_list[i]
                    # 清理文件名（移除不允许的字符）
                    import re
                    base_filename = re.sub(r'[<>:"/\\|?*]', '_', base_filename)
                    filename = f"{base_filename}{file_extension}"
                else:
                    # 如果图像文件名不足，使用编号作为后备
                    num_str = str(i + 1).zfill(filename_padding)
                    filename = (
                        f"{filename_prefix}{filename_separator}{num_str}{filename_suffix}{file_extension}"
                    )
                    print(f"[MIKKYSaveLogsList] Warning: No image filename for index {i}, using numbered name")
                
                full_path = os.path.join(save_dir, filename)
                
                # 如果避免覆盖且文件已存在，添加后缀
                if avoid_overwrite and os.path.exists(full_path):
                    base_name = os.path.splitext(filename)[0]
                    counter = 1
                    while os.path.exists(full_path):
                        filename = f"{base_name}_{counter}{file_extension}"
                        full_path = os.path.join(save_dir, filename)
                        counter += 1
                        if counter > 10000:
                            import time
                            timestamp = int(time.time() * 1000)
                            filename = f"{base_name}_{timestamp}{file_extension}"
                            full_path = os.path.join(save_dir, filename)
                            break
            elif avoid_overwrite:
                # 从起始编号开始，查找可用文件名
                current_index = start_index + i
                max_attempts = 10000  # 防止无限循环
                attempts = 0
                
                while attempts < max_attempts:
                    num_str = str(current_index).zfill(filename_padding)
                    filename = (
                        f"{filename_prefix}{filename_separator}{num_str}{filename_suffix}{file_extension}"
                    )
                    full_path = os.path.join(save_dir, filename)
                    
                    if not os.path.exists(full_path):
                        # 找到可用文件名
                        break
                    current_index += 1
                    attempts += 1
                
                if attempts >= max_attempts:
                    # 如果找不到可用文件名，使用时间戳
                    import time
                    timestamp = int(time.time() * 1000)  # 毫秒时间戳
                    num_str = str(start_index + i).zfill(filename_padding)
                    filename = (
                        f"{filename_prefix}{filename_separator}{num_str}{filename_separator}{timestamp}{filename_suffix}{file_extension}"
                    )
                    full_path = os.path.join(save_dir, filename)
                    print(f"[MIKKYSaveLogsList] Warning: Using timestamp for filename to avoid conflict")
            else:
                # 不避免覆盖，使用原始编号
                num_str = str(i + 1).zfill(filename_padding)
                filename = (
                    f"{filename_prefix}{filename_separator}{num_str}{filename_suffix}{file_extension}"
                )
                full_path = os.path.join(save_dir, filename)

            try:
                with open(full_path, "w", encoding=encoding) as f:
                    f.write(text)
                saved_paths.append(full_path)
                print(f"[MIKKYSaveLogsList] Saved: {full_path}")
            except Exception as e:
                error_msg = f"[MIKKYSaveLogsList] Failed to save {full_path}: {e}"
                print(error_msg)
                saved_paths.append(f"[ERROR] {full_path}")

        result_str = "\n".join(saved_paths)
        print(f"[MIKKYSaveLogsList] ✅ All {len(saved_paths)} files saved to: {save_dir}")
        return (result_str,)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYSaveLogsList": MIKKYSaveLogsList
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYSaveLogsList": "MIKKY Save Logs List"
}

