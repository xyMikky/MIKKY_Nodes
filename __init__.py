# MIKKY Nodes - 整合所有ComfyUI插件节点
# 自动导入所有节点文件

import importlib
import os

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 所有节点文件列表（按顺序）
node_files = [
    "01_average_split_node",
    "02_batch_utils",
    "03_frame_aligner",
    "05_imagejudge",
    "07_mask_batcher",
    "08_video_iterator",
    "09_wan_image_viewer",
    "10_mask_editor",
    "11_banana_utils",
    "12_extract_float",
    "14_mikky_image",
    "15_video_seg",
    "16_siliconflow_tagger",
    "17_split_options",
    "18_image_resize_duplicate",
    "19_video_side_splitter",
    "20_storyboard_extractor",
    "21_savelogs",
    "22_load_images_from_folder",
    "23_video_merger",
]

# 合并所有节点的映射
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# 逐个导入节点文件
for node_file in node_files:
    try:
        module = importlib.import_module(f".{node_file}", package=__name__)
        
        # 合并节点映射
        if hasattr(module, "NODE_CLASS_MAPPINGS"):
            NODE_CLASS_MAPPINGS.update(module.NODE_CLASS_MAPPINGS)
        
        if hasattr(module, "NODE_DISPLAY_NAME_MAPPINGS"):
            NODE_DISPLAY_NAME_MAPPINGS.update(module.NODE_DISPLAY_NAME_MAPPINGS)
            
        print(f"[MIKKY Nodes] Loaded: {node_file}")
    except Exception as e:
        print(f"[MIKKY Nodes] Error loading {node_file}: {e}")

print(f"[MIKKY Nodes] Total nodes loaded: {len(NODE_CLASS_MAPPINGS)}")

# 设置JS文件目录
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

