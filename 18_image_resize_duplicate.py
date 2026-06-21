"""
ImageResizeAndDuplicate
=======================

ComfyUI 自定义节点：
将输入图像按照设定最大边长进行等比例缩放，
并复制为指定数量的输出图像。
"""

import torch
import numpy as np
from PIL import Image
import io


class MIKKYImageResizeAndDuplicate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "max_side": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 64}),
                "num_copies": ("INT", {"default": 6, "min": 1, "max": 100}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "resize_and_duplicate"
    CATEGORY = "MIKKY nodes/Image Transform"
    DESCRIPTION = "按最大边长缩放图像并复制多份"

    def resize_and_duplicate(self, image: torch.Tensor, max_side: int, num_copies: int):
        """执行图像缩放与复制"""

        if image.ndim == 4:
            image = image[0]  # 取第一张
        img_np = (image.cpu().numpy().clip(0, 1) * 255).astype(np.uint8)

        # 处理 RGBA 情况
        if img_np.shape[-1] == 4:
            img_pil = Image.fromarray(img_np[:, :, :3])
        else:
            img_pil = Image.fromarray(img_np)

        w, h = img_pil.size
        scale = max_side / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img_resized = img_pil.resize((new_w, new_h), Image.LANCZOS)

        # 转换回 Tensor
        img_tensor = torch.from_numpy(np.array(img_resized).astype(np.float32) / 255.0)
        img_tensor = img_tensor.unsqueeze(0)  # [1, H, W, C]

        # 复制指定数量
        output_images = [img_tensor.clone() for _ in range(num_copies)]
        output_tensor = torch.cat(output_images, dim=0)

        print(f"[ImageResizeAndDuplicate] 原始尺寸: {w}x{h} -> 缩放后: {new_w}x{new_h}, 输出数量: {num_copies}")
        return (output_tensor,)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYImageResizeAndDuplicate": MIKKYImageResizeAndDuplicate
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYImageResizeAndDuplicate": "MIKKY Image Resize & Duplicate"
}

