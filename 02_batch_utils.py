import torch
import math


class MIKKYBatchImageStride:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "interval": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "display": "number"
                }),
                "start_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "display": "number"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "process"
    CATEGORY = "MIKKY nodes/Batch Utils"

    def process(self, images, interval, start_index):
        # images shape: [Batch, Height, Width, Channel]

        # 确保起始索引在范围内
        if start_index >= len(images):
            # 如果起始索引超出范围，返回最后一张图作为保底，或者报错
            # 这里选择返回空batch会有问题，所以返回最后一张
            print(f"Warning: start_index {start_index} is out of bounds. Using last image.")
            return (images[-1].unsqueeze(0),)

        # Python 切片语法: list[start:end:step]
        # 例如输入10张，interval为3，start为0 -> index: 0, 3, 6, 9 (即第1,4,7,10张)
        selected_images = images[start_index::interval]

        return (selected_images,)


class MIKKYBatchImageFusion:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "mode": (["Grid (Tiled)", "Overlay (Average)", "Difference (from first)"],),
                "columns": ("INT", {
                    "default": 4,
                    "min": 1,
                    "max": 50,
                    "step": 1
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("fused_image",)
    FUNCTION = "process"
    CATEGORY = "MIKKY nodes/Batch Utils"

    def process(self, images, mode, columns):
        # ComfyUI images shape: [B, H, W, C]
        batch_size, height, width, channels = images.shape

        if batch_size == 0:
            return (torch.zeros((1, 512, 512, 3)),)

        if mode == "Grid (Tiled)":
            # 网格模式：将图片拼接成大图
            cols = min(columns, batch_size)
            rows = math.ceil(batch_size / cols)

            # 创建画布
            grid_h = rows * height
            grid_w = cols * width
            grid_image = torch.zeros((1, grid_h, grid_w, channels), dtype=images.dtype, device=images.device)

            for idx, img in enumerate(images):
                r = idx // cols
                c = idx % cols

                start_y = r * height
                end_y = start_y + height
                start_x = c * width
                end_x = start_x + width

                grid_image[0, start_y:end_y, start_x:end_x, :] = img

            return (grid_image,)

        elif mode == "Overlay (Average)":
            # 叠加模式：计算所有图片的平均值
            # 这种模式下，不变的地方会清晰，变化的地方会变模糊/重影，非常适合观察差异
            mean_image = torch.mean(images, dim=0, keepdim=True)
            return (mean_image,)

        elif mode == "Difference (from first)":
            # 差异模式：显示所有图片相对于第一张图的差异程度
            # 结果越亮，代表与第一张图差异越大
            base_image = images[0].unsqueeze(0)  # 取第一张作为基准
            diff_tensor = torch.abs(images - base_image)

            # 这里可以选择返回平均差异图，或者是差异图的Grid
            # 为了方便看，我们返回平均差异图，这能显示出"整个批次中哪里在变动"
            mean_diff = torch.mean(diff_tensor, dim=0, keepdim=True)

            # 稍微增强一下亮度以便观察，否则微小的差异看不清
            mean_diff = mean_diff * 2.0
            mean_diff = torch.clamp(mean_diff, 0, 1)

            return (mean_diff,)

        return (images,)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYBatchImageStride": MIKKYBatchImageStride,
    "MIKKYBatchImageFusion": MIKKYBatchImageFusion
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYBatchImageStride": "MIKKY Batch Image Stride",
    "MIKKYBatchImageFusion": "MIKKY Batch Image Fusion"
}

