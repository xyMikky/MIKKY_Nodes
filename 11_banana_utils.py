import torch
import torch.nn.functional as F
import numpy as np

# ==========================================
# 节点 1: 智能裁切 (BananaSmartCrop)
# ==========================================
class MIKKYBananaSmartCrop:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "context_expand_factor": ("FLOAT", {
                    "default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01
                }),
                "force_ratio": (["Auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],),
            },
        }

    # 新增了 "cropped_mask" 输出
    RETURN_TYPES = ("MASK", "IMAGE", "MASK", "STRING", "BOX")
    RETURN_NAMES = ("box_mask_full", "cropped_image", "cropped_mask", "chosen_ratio", "crop_box_xywh")

    FUNCTION = "calculate_crop"
    CATEGORY = "MIKKY nodes/Banana Utils"

    def calculate_crop(self, image, mask, context_expand_factor, force_ratio):
        RATIOS = {
            "1:1": 1.0, "2:3": 2 / 3, "3:2": 3 / 2, "3:4": 3 / 4, "4:3": 4 / 3,
            "4:5": 4 / 5, "5:4": 5 / 4, "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9
        }

        # 处理 Mask 维度 [H, W] -> [1, H, W]
        if mask.dim() == 2:
            mask = mask.unsqueeze(0)

        orig_h, orig_w = image.shape[1], image.shape[2]

        # 1. 计算 Bounding Box
        rows, cols = torch.where(mask[0] > 0.5)
        if len(rows) == 0:
            print("Warning: Empty mask. Using center crop.")
            min_y, max_y = orig_h // 4, orig_h * 3 // 4
            min_x, max_x = orig_w // 4, orig_w * 3 // 4
        else:
            min_y, max_y = rows.min().item(), rows.max().item()
            min_x, max_x = cols.min().item(), cols.max().item()

        # 2. 扩大范围 (Context Expand)
        box_w = max_x - min_x
        box_h = max_y - min_y
        pad_w = int(box_w * context_expand_factor)
        pad_h = int(box_h * context_expand_factor)

        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2

        target_w = box_w + (pad_w * 2)
        target_h = box_h + (pad_h * 2)

        # 3. 匹配长宽比
        current_ratio = target_w / max(1, target_h)
        chosen_ratio_name = "1:1"
        target_ratio_val = 1.0

        if force_ratio != "Auto":
            chosen_ratio_name = force_ratio
            target_ratio_val = RATIOS[force_ratio]
        else:
            closest_diff = float('inf')
            for name, val in RATIOS.items():
                diff = abs(val - current_ratio)
                if diff < closest_diff:
                    closest_diff = diff
                    chosen_ratio_name = name
                    target_ratio_val = val

        # 4. 调整尺寸 (Expand)
        if (target_w / target_h) > target_ratio_val:
            new_h = target_w / target_ratio_val
            new_w = target_w
        else:
            new_w = target_h * target_ratio_val
            new_h = target_h

        final_w = int(new_w)
        final_h = int(new_h)

        # 5. 计算坐标 & Clamp
        x1 = center_x - (final_w // 2)
        y1 = center_y - (final_h // 2)
        x2 = x1 + final_w
        y2 = y1 + final_h

        # Shift
        if x1 < 0: x2 += abs(x1); x1 = 0
        if y1 < 0: y2 += abs(y1); y1 = 0
        if x2 > orig_w: x1 -= (x2 - orig_w); x2 = orig_w
        if y2 > orig_h: y1 -= (y2 - orig_h); y2 = orig_h

        # Hard Clamp
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(orig_w, int(x2)), min(orig_h, int(y2))

        real_w = x2 - x1
        real_h = y2 - y1
        
        # 修正：在 clamp 后重新调整以保持目标比例
        # 如果实际区域的比例与目标比例不一致，需要进一步收缩以保持比例
        actual_ratio = real_w / max(1, real_h)
        if abs(actual_ratio - target_ratio_val) > 0.01:  # 允许1%的误差
            if actual_ratio > target_ratio_val:
                # 实际宽度相对太大，需要缩小宽度
                new_real_w = int(real_h * target_ratio_val)
                diff = real_w - new_real_w
                x1 += diff // 2
                x2 -= diff - (diff // 2)
                real_w = x2 - x1
            else:
                # 实际高度相对太大，需要缩小高度
                new_real_h = int(real_w / target_ratio_val)
                diff = real_h - new_real_h
                y1 += diff // 2
                y2 -= diff - (diff // 2)
                real_h = y2 - y1

        # 6. 生成输出
        # 全图大小的 Box Mask (仅供预览用)
        box_mask_full = torch.zeros((1, orig_h, orig_w), dtype=torch.float32)
        box_mask_full[:, y1:y2, x1:x2] = 1.0

        # 裁切后的图像
        cropped_image = image[:, y1:y2, x1:x2, :]

        # 裁切后的 Mask (这是最重要的，用来告诉 API 在这个小图里哪里是需要修的)
        cropped_mask = mask[:, y1:y2, x1:x2]

        crop_box = [x1, y1, real_w, real_h]

        return (box_mask_full, cropped_image, cropped_mask, chosen_ratio_name, crop_box)


# ==========================================
# 节点 2: 智能回贴 (BananaUncropPaste) - v3.0 (Stretch Mode)
# ==========================================
class MIKKYBananaUncropPaste:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "original_image": ("IMAGE",),
                "processed_crop_image": ("IMAGE",),  # API 返回的大图
                "crop_box_xywh": ("BOX",),  # 节点 1 的输出
                "feather": ("INT", {"default": 16, "min": 0, "max": 200, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "paste_back"
    CATEGORY = "MIKKY nodes/Banana Utils"

    def paste_back(self, original_image, processed_crop_image, crop_box_xywh, feather):
        # original_image: [B, H, W, C]
        # processed_crop_image: [B, H_api, W_api, C]

        x, y, target_w, target_h = crop_box_xywh

        # ============================================================
        # 核心修改：强制拉伸对齐 (Direct Stretch to Fit)
        # ============================================================
        # 不计算宽高比，不进行裁切 (No Crop)。
        # 无论 API 返回什么比例，都强制拉伸/压缩到目标框的大小。
        # 这是为了确保"长边不发生改变"(即不裁切长边)，同时"fill"(填满)短边。

        # 1. 维度调整 [B, H, W, C] -> [B, C, H, W] 以供 interpolate 使用
        img_tensor = processed_crop_image.permute(0, 3, 1, 2)

        # 2. 强制插值到目标尺寸 (target_h, target_w)
        # 使用 bicubic + antialias 以获得最佳的形变画质，减少拉伸带来的模糊
        resized_tensor = F.interpolate(
            img_tensor,
            size=(target_h, target_w),
            mode='bicubic',
            align_corners=False,
            antialias=True
        )

        # 3. 变回 ComfyUI 图像格式 [B, H, W, C]
        final_paste_image = resized_tensor.permute(0, 2, 3, 1)

        # ============================================================
        # 后续逻辑：羽化与合成
        # ============================================================
        
        # 通道对齐：确保 final_paste_image 与 original_image 通道数一致
        if final_paste_image.shape[3] != original_image.shape[3]:
            if final_paste_image.shape[3] == 4 and original_image.shape[3] == 3:
                # 去除 alpha 通道，只保留 RGB
                final_paste_image = final_paste_image[:, :, :, :3]
            elif final_paste_image.shape[3] == 3 and original_image.shape[3] == 4:
                # 添加 alpha 通道（全不透明）
                alpha_channel = torch.ones((final_paste_image.shape[0], final_paste_image.shape[1], 
                                           final_paste_image.shape[2], 1), dtype=final_paste_image.dtype)
                final_paste_image = torch.cat([final_paste_image, alpha_channel], dim=3)

        # 准备画布
        output_image = original_image.clone()

        # Batch 广播
        if output_image.shape[0] != final_paste_image.shape[0]:
            final_paste_image = final_paste_image[0].unsqueeze(0)

        # 创建羽化遮罩
        # 此时 final_paste_image 的尺寸严格等于 target_w, target_h，无需再次校验
        mask_h, mask_w = target_h, target_w

        if feather > 0:
            Y = torch.linspace(0, mask_h - 1, mask_h).view(mask_h, 1).repeat(1, mask_w)
            X = torch.linspace(0, mask_w - 1, mask_w).view(1, mask_w).repeat(mask_h, 1)

            dist_top = Y
            dist_bottom = mask_h - 1 - Y
            dist_left = X
            dist_right = mask_w - 1 - X

            min_dist = torch.min(torch.min(dist_top, dist_bottom), torch.min(dist_left, dist_right))
            alpha_mask = torch.clamp(min_dist / feather, 0.0, 1.0)
            alpha_mask = alpha_mask.unsqueeze(0).unsqueeze(-1)
        else:
            alpha_mask = torch.ones((1, mask_h, mask_w, 1), dtype=torch.float32)

        # 图像合成
        original_area = output_image[:, y:y + target_h, x:x + target_w, :]

        # 混合: (API图 * Mask) + (原图 * (1-Mask))
        blended_area = final_paste_image * alpha_mask + original_area * (1.0 - alpha_mask)

        output_image[:, y:y + target_h, x:x + target_w, :] = blended_area

        return (output_image,)
    
# ==========================================
# 注册节点
# ==========================================
NODE_CLASS_MAPPINGS = {
    "MIKKYBananaSmartCrop": MIKKYBananaSmartCrop,
    "MIKKYBananaUncropPaste": MIKKYBananaUncropPaste
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYBananaSmartCrop": "MIKKY 🍌 Banana Smart Crop",
    "MIKKYBananaUncropPaste": "MIKKY 🍌 Banana Uncrop Paste"
}

