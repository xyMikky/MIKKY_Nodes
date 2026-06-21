import re
import json


class MIKKYExtractFloatFromText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True}),
            }
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "extract_float"
    CATEGORY = "MIKKY nodes/Utils"
    DESCRIPTION = "从文本中提取第一个浮点数，保留两位小数"

    def extract_float(self, text):
        # 使用正则表达式匹配浮点数（包括负数、科学计数法等）
        pattern = r'[-+]?\d*\.\d+|\d+'
        match = re.search(pattern, text)

        if match:
            try:
                value = float(match.group())
                # 保留两位小数
                rounded_value = round(value, 2)
                return (rounded_value,)
            except ValueError:
                pass

        # 如果没有找到有效浮点数，返回 0.00
        return (0.0,)


# 注册节点
NODE_CLASS_MAPPINGS = {
    "MIKKYExtractFloatFromText": MIKKYExtractFloatFromText
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYExtractFloatFromText": "MIKKY Extract Float from Text"
}

