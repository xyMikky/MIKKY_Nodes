import torch
import os
import folder_paths
import numpy as np
from PIL import Image
import random


class MIKKYWanBatchImageViewer:
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_wan_temp_"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "index": ("INT", {"default": 0, "min": 0, "max": 9999, "step": 1, "display": "number"}),
            },
            "hidden": {
                "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("selected_image",)
    FUNCTION = "process_images"
    OUTPUT_NODE = True
    CATEGORY = "MIKKY nodes/Image Viewer"

    def process_images(self, images, index, prompt=None, extra_pnginfo=None):
        # 1. 处理输出逻辑
        batch_count = images.shape[0]
        # 容错处理
        if batch_count == 0:
            return (torch.zeros((1, 64, 64, 3)),)

        target_index = index % batch_count  # 确保索引不越界
        selected_image = images[target_index:target_index + 1]

        # 2. 处理预览逻辑 (保存图片供前端显示)
        results = list()
        for i in range(batch_count):
            img_tensor = images[i]
            # 转换为 PIL Image
            i_np = 255. * img_tensor.cpu().numpy()
            img = Image.fromarray(np.clip(i_np, 0, 255).astype(np.uint8))

            # 保存到临时目录
            filename = f"wan_preview_{random.randint(100000, 999999)}_{i}.png"
            full_path = os.path.join(self.output_dir, filename)
            img.save(full_path)

            results.append({
                "filename": filename,
                "subfolder": "",
                "type": self.type
            })

        # 3. 返回给前端的数据
        # 关键修改：将键名从 "images" 改为 "wan_thumbnails"，避免触发 ComfyUI 默认预览
        return {
            "ui": {
                "wan_thumbnails": results,
                "selected_index": [target_index]
            },
            "result": (selected_image,)
        }


NODE_CLASS_MAPPINGS = {
    "MIKKYWanBatchImageViewer": MIKKYWanBatchImageViewer
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYWanBatchImageViewer": "MIKKY Wan Batch Gallery Selector"
}

