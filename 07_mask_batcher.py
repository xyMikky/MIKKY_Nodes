import torch
import comfy
import math
import numpy as np
import cv2


class MIKKYMaskBatcherAndBBoxNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mask": ("MASK",),  # [H, W] or [1, H, W]
                "mode": (["original", "bbox", "square"], {
                    "default": "original",
                    "tooltip": "original: keep as-is; bbox: tight rectangle; square: square centered on bbox"
                }),
                "count": ("INT", {"default": 1, "min": 1, "max": 1000, "step": 1}),
                "padding": ("INT", {"default": 0, "min": 0, "max": 1000, "step": 1,
                                    "tooltip": "Extra px padding around bbox/square"}),
            },
            "optional": {
                "force_binary": ("BOOLEAN",
                                 {"default": True, "tooltip": "Threshold mask > 0.5 → binary before bbox detection"}),
            }
        }

    RETURN_TYPES = ("MASK",)
    FUNCTION = "execute"
    CATEGORY = "MIKKY nodes/Mask"
    DESCRIPTION = "Convert irregular mask to bbox/square mask, then repeat to batch."

    def execute(self, mask, mode="original", count=1, padding=0, force_binary=True):
        # Normalize input mask → [1, H, W]
        if mask.ndim == 2:
            mask = mask.unsqueeze(0)  # [H, W] → [1, H, W]
        elif mask.ndim == 3:
            if mask.shape[0] != 1:
                # Take first if batch (warn? but comfy often passes batch)
                mask = mask[:1]
        else:
            raise ValueError(f"Unsupported mask dim: {mask.ndim}")

        mask = mask.clone()  # avoid inplace
        H, W = mask.shape[1], mask.shape[2]

        # Optional: binary threshold
        if force_binary:
            mask = (mask > 0.5).float()

        if mode == "original":
            processed_mask = mask  # [1, H, W]
        else:
            # Create a blank canvas for the new mask
            new_mask = torch.zeros_like(mask[0])  # [H, W]

            # Convert to numpy for contour finding (much easier with OpenCV)
            mask_np = mask[0].cpu().numpy()
            # Ensure strictly binary uint8
            mask_np = (mask_np > 0).astype(np.uint8) * 255

            # Find contours (separate islands)
            # RETR_EXTERNAL: only outer contours
            contours, _ = cv2.findContours(mask_np, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                # No foreground → return full image (matching original logic fallback)
                new_mask[:, :] = 1.0
            else:
                # Loop through EACH separate mask island
                for cnt in contours:
                    # Get bbox for this specific contour
                    x, y, w, h = cv2.boundingRect(cnt)
                    x1, y1, x2, y2 = x, y, x + w, y + h

                    # Apply padding (clamp to image bounds)
                    x1 = max(0, x1 - padding)
                    y1 = max(0, y1 - padding)
                    x2 = min(W, x2 + padding)
                    y2 = min(H, y2 + padding)

                    if mode == "square":
                        # Make THIS bbox square: expand shorter side to match longer
                        w_box, h_box = x2 - x1, y2 - y1
                        size = max(w_box, h_box)
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        half = size // 2

                        x1_sq = max(0, cx - half)
                        y1_sq = max(0, cy - half)
                        x2_sq = min(W, x1_sq + size)
                        y2_sq = min(H, y1_sq + size)

                        # Final adjust to keep square if clipped by image edge
                        final_size = min(x2_sq - x1_sq, y2_sq - y1_sq)
                        x2_sq = x1_sq + final_size
                        y2_sq = y1_sq + final_size
                        x1, y1, x2, y2 = x1_sq, y1_sq, x2_sq, y2_sq

                    # Draw this box onto the canvas (using max to combine overlapping boxes)
                    new_mask[y1:y2, x1:x2] = 1.0

            processed_mask = new_mask.unsqueeze(0)  # [1, H, W]

        # Batch repeat → [count, H, W]
        mask_batch = processed_mask.repeat(count, 1, 1)

        return (mask_batch,)


# ———————————— 节点注册 ————————————

NODE_CLASS_MAPPINGS = {
    "MIKKYMaskBatcherAndBBox": MIKKYMaskBatcherAndBBoxNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYMaskBatcherAndBBox": "MIKKY RGBO Mask Batcher + BBox 🖼️→🟥×N",
}

