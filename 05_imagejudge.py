import torch
from PIL import Image
import numpy as np

class MIKKYImageLimitMaxSizeLanczos:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "max_size": ("INT", {"default": 1500, "min": 1, "max": 8192, "step": 1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "limit_max_size"
    CATEGORY = "MIKKY nodes/Image Transform"

    def limit_max_size(self, image: torch.Tensor, max_size: int):
        """
        Resize image with Lanczos interpolation if max(H, W) > max_size.
        Input/Output: [B, H, W, C] tensor in [0, 1] range.
        """
        if image.ndim != 4:
            raise ValueError("Input image must be a 4D tensor [B, H, W, C]")

        B, H, W, C = image.shape
        current_max = max(H, W)

        if current_max <= max_size:
            return (image,)

        scale = max_size / current_max
        new_h = int(round(H * scale))
        new_w = int(round(W * scale))

        # Ensure at least 1 pixel
        new_h = max(1, new_h)
        new_w = max(1, new_w)

        # Convert to numpy for PIL processing (detach if needed)
        image_np = image.cpu().numpy()  # [B, H, W, C]

        resized_batch = []
        for i in range(B):
            img_array = image_np[i]  # [H, W, C]
            # Convert to uint8 [0, 255]
            img_uint8 = (img_array * 255).clip(0, 255).astype(np.uint8)
            pil_img = Image.fromarray(img_uint8)
            # Lanczos resampling
            resized_pil = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # Back to float32 [0, 1]
            resized_array = np.array(resized_pil).astype(np.float32) / 255.0
            resized_batch.append(resized_array)

        # Stack and convert back to tensor
        resized_np = np.stack(resized_batch, axis=0)  # [B, H', W', C]
        resized_tensor = torch.from_numpy(resized_np).to(image.device, dtype=image.dtype)

        return (resized_tensor,)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYImageLimitMaxSizeLanczos": MIKKYImageLimitMaxSizeLanczos
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYImageLimitMaxSizeLanczos": "MIKKY Limit Image Max Size (Lanczos)"
}

