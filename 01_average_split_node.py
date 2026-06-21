# ComfyUI 自定义节点：计算最佳平均分割值（≤90）
import math
import comfy.utils

class MIKKYAverageSplitNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "total_value": ("INT", {"default": 350, "min": 1, "max": 1000000, "step": 1}),
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("best_average_value",)
    FUNCTION = "compute"
    CATEGORY = "MIKKY nodes/Utils"

    def compute(self, total_value):
        if total_value <= 0:
            raise ValueError("Input value must be a positive integer.")

        # 最小分割份数，使得每份不超过90
        k_min = math.ceil(total_value / 90)

        # 对应的最佳平均值（向上取整，确保总和不小于原值）
        best_avg = math.ceil(total_value / k_min)

        # 理论上 best_avg <= 90，但加个保险
        if best_avg > 90:
            best_avg = 90

        return (best_avg,)

# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYAverageSplitNode": MIKKYAverageSplitNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYAverageSplitNode": "MIKKY Average Split (≤90)"
}

