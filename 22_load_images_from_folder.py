"""
MIKKY Load Images From Folder - 从文件夹加载图像节点
从指定文件夹路径加载所有图像文件，输出图像批次和对应的文件名（不含扩展名）
"""
import os
import torch
import numpy as np
from PIL import Image, ImageOps
import folder_paths
from typing import List, Tuple


# 支持的图像扩展名
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.tif')


def get_image_files(folder_path):
    """获取文件夹中所有图像文件的路径"""
    if not os.path.isdir(folder_path):
        return []
    
    files = []
    for f in os.listdir(folder_path):
        if f.lower().endswith(IMAGE_EXTENSIONS):
            files.append(os.path.join(folder_path, f))
    
    # 按文件名排序
    files.sort()
    return files


class MIKKYLoadImagesFromFolder:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {
                    "default": "",
                    "tooltip": "图像文件夹路径（绝对路径或相对于ComfyUI根目录）"
                }),
            },
            "optional": {
                "image_load_limit": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 10000,
                    "step": 1,
                    "tooltip": "图像加载上限（0表示加载所有图像）"
                }),
                "starting_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 10000,
                    "step": 1,
                    "tooltip": "起始索引（从第几个图像开始加载，从0开始）"
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "filenames")
    OUTPUT_IS_LIST = (True, True)  # 标记输出为列表类型
    FUNCTION = "load_images"
    CATEGORY = "MIKKY nodes/Image Input"
    DESCRIPTION = "从文件夹路径加载所有图像文件，输出图像列表（支持不同尺寸）和对应的文件名（不含扩展名）"

    def load_images(self, folder_path: str, image_load_limit: int = 0, starting_index: int = 0):
        """加载文件夹中的图像，返回图像列表（支持不同尺寸）"""
        
        if not folder_path or not folder_path.strip():
            print("[MIKKYLoadImagesFromFolder] Warning: Empty folder path")
            return ([], "")
        
        # 处理路径
        folder_path = folder_path.strip()
        
        # 如果是相对路径，尝试相对于ComfyUI根目录
        if not os.path.isabs(folder_path):
            # 尝试相对于ComfyUI的输入目录
            input_dir = folder_paths.get_input_directory()
            possible_path = os.path.join(input_dir, folder_path)
            if os.path.isdir(possible_path):
                folder_path = possible_path
            else:
                # 尝试相对于ComfyUI根目录
                comfy_root = os.path.dirname(os.path.dirname(input_dir)) if os.path.dirname(input_dir) else input_dir
                possible_path = os.path.join(comfy_root, folder_path)
                if os.path.isdir(possible_path):
                    folder_path = possible_path
        
        if not os.path.isdir(folder_path):
            error_msg = f"[MIKKYLoadImagesFromFolder] Error: Folder not found: {folder_path}"
            print(error_msg)
            return ([], "")
        
        # 获取所有图像文件
        image_files = get_image_files(folder_path)
        
        if len(image_files) == 0:
            print(f"[MIKKYLoadImagesFromFolder] Warning: No image files found in {folder_path}")
            return ([], "")
        
        print(f"[MIKKYLoadImagesFromFolder] Found {len(image_files)} image files in {folder_path}")
        
        # 应用起始索引和加载上限
        if starting_index > 0:
            image_files = image_files[starting_index:]
            print(f"[MIKKYLoadImagesFromFolder] Starting from index {starting_index}, {len(image_files)} files remaining")
        
        if image_load_limit > 0 and len(image_files) > image_load_limit:
            image_files = image_files[:image_load_limit]
            print(f"[MIKKYLoadImagesFromFolder] Limited to {image_load_limit} images")
        
        # 加载所有图像（不进行任何修改）
        images = []
        filenames = []
        sizes = []
        
        for img_path in image_files:
            try:
                # 加载图像（参照 LoadImagesFromDirList 的方式）
                i = Image.open(img_path)
                i = ImageOps.exif_transpose(i)  # 处理 EXIF 方向信息
                image = i.convert("RGB")
                image = np.array(image).astype(np.float32) / 255.0
                image = torch.from_numpy(image)[None,]  # [1, H, W, C] 格式
                
                h, w, c = image.shape[1], image.shape[2], image.shape[3]
                images.append(image)  # 保持 [1, H, W, C] 格式
                sizes.append((h, w))
                
                # 提取文件名（不含扩展名）
                filename = os.path.splitext(os.path.basename(img_path))[0]
                filenames.append(filename)
                
            except Exception as e:
                print(f"[MIKKYLoadImagesFromFolder] Warning: Failed to load {img_path}: {e}")
                continue
        
        if len(images) == 0:
            print(f"[MIKKYLoadImagesFromFolder] Error: No images were successfully loaded")
            return ([], "")
        
        # 显示图像尺寸信息
        unique_sizes = set(sizes)
        if len(unique_sizes) == 1:
            print(f"[MIKKYLoadImagesFromFolder] All images have same size: {sizes[0]}")
        else:
            print(f"[MIKKYLoadImagesFromFolder] Images have different sizes: {unique_sizes}")
            print(f"[MIKKYLoadImagesFromFolder] ✅ Using list output - different sizes are supported")
        
        print(f"[MIKKYLoadImagesFromFolder] ✅ Successfully loaded {len(images)} images")
        print(f"[MIKKYLoadImagesFromFolder] Filenames: {', '.join(filenames)}")
        
        # 返回图像列表和文件名列表（参照 LoadImagesFromDirList 的方式）
        # images 是 List[[1, H, W, C]]，filenames 是 List[str]
        return (images, filenames)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYLoadImagesFromFolder": MIKKYLoadImagesFromFolder
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYLoadImagesFromFolder": "MIKKY Load Images From Folder"
}

