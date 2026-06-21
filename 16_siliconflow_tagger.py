"""
MIKKY SiliconFlow Async Tagger (List Output Version)
============================================

真正异步并发的 SiliconFlow Qwen3-VL 图像打标器。
支持 ComfyUI、Jupyter 等环境。

输出结果为 list，对应每张图片的打标文本。
"""

import base64
import io
import asyncio
import aiohttp
import time
import nest_asyncio  # ✅ 允许嵌套事件循环
from PIL import Image
import numpy as np
import torch
from typing import List, Tuple
from collections import deque

# 允许在已有事件循环中运行异步任务
nest_asyncio.apply()


class RateLimiter:
    """速率限制器 - 基于滑动窗口算法（异步版本）
    
    根据 API 限制控制请求速率：
    - RPM: 1000 请求/分钟 = 16.67 请求/秒
    - 支持真正的并发：在限制内允许立即执行，超过限制时才等待
    """
    def __init__(self, rpm_limit: int = 1000, tpm_limit: int = 10000):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        
        # 请求时间戳队列（用于滑动窗口）
        self.request_times = deque()
        self.lock = asyncio.Lock()
        self.window_size = 60.0  # 60秒窗口
        
    async def acquire(self):
        """获取一个请求令牌（异步版本）
        
        优化策略：
        1. 快速检查是否有空间（在锁内，但尽量快）
        2. 如果有空间，立即返回（不等待）
        3. 如果没有空间，计算等待时间并在锁外等待
        4. 使用宽松的阈值（95%），允许在接近限制时继续执行
        """
        max_retries = 1000  # 防止无限循环
        retry_count = 0
        
        while retry_count < max_retries:
            now = time.time()
            
            # 快速检查（尽量缩短锁的持有时间）
            async with self.lock:
                # 清理过期的请求时间戳（60秒窗口）
                while self.request_times and (now - self.request_times[0]) > self.window_size:
                    self.request_times.popleft()
                
                # 检查是否还有空间（使用95%的阈值，更宽松，允许突发）
                current_count = len(self.request_times)
                threshold = int(self.rpm_limit * 0.95)  # 95%阈值
                
                if current_count < threshold:
                    # 有空间，立即允许请求
                    self.request_times.append(now)
                    return  # 成功获取令牌，立即返回
                
                # 没有空间，计算需要等待的时间
                if self.request_times:
                    oldest_time = self.request_times[0]
                    # 计算需要等待的时间（直到最老的请求过期）
                    wait_time = self.window_size - (now - oldest_time) + 0.05  # 加50ms缓冲
                else:
                    wait_time = 0.05
            
            # 在锁外等待（关键：不在锁内等待，允许其他任务继续检查）
            if wait_time > 0:
                # 分段等待，每50ms检查一次，避免长时间阻塞
                wait_chunk = min(wait_time, 0.05)
                await asyncio.sleep(wait_chunk)
            
            retry_count += 1
        
        # 如果重试次数过多，强制允许（避免死锁）
        async with self.lock:
            self.request_times.append(time.time())
            print(f"[RateLimiter] Warning: Max retries reached, allowing request anyway")


class MIKKYSiliconFlowAsyncTagger:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": """你是一位AI图像打标专家，专为LoRA模型的概念学习生成定向标签。用户会提供三部分输入：(1) 图像描述，(2) 可选触发词（任意字符串），(3) 本次打标的核心概念（如"身材""面料""姿态"）。

请严格遵循：
1. **触发词处理**：若提供触发词，原样置于开头，后接", "。
2. **概念聚焦**：优先详细描述用户指定的"核心概念"（如"身材"需突出体型、曲线、比例），其他元素（背景、表情等）仅简要带过。
3. **长度控制**：总输出必须为2–4个英文句子，总词数严格少于80。
4. **语言规范**：使用标准英文标点（允许逗号、句号），禁用感叹号、问号、引号；内容必须基于图像事实，不虚构。

示例：
输入：触发词=2erqs，核心概念=身材，图像描述=棕发女性穿黑色塑身衣站白背景前，马尾，微笑，一手放腿上  
输出：2erqs, A woman with an hourglass figure wears a black waist trainer that accentuates her narrow waist and full hips. Her toned abdomen and smooth skin are highlighted under soft studio lighting. She stands confidently with one hand on her thigh, showcasing her body shape against a plain white background."""
                }),
                "user_instruction": ("STRING", {
                    "multiline": True,
                    "default": ""
                }),
                "api_token": ("STRING", {"default": ""}),
                "max_concurrent": ("INT", {
                    "default": 15,
                    "min": 1,
                    "max": 50,
                    "tooltip": "最大并发请求数。建议值：10-20。API限制：RPM=1000, TPM=10000"
                }),
                "timeout": ("INT", {
                    "default": 120,
                    "min": 30,
                    "max": 300,
                    "tooltip": "单个请求的超时时间（秒）"
                }),
                "rpm_limit": ("INT", {
                    "default": 1000,
                    "min": 100,
                    "max": 10000,
                    "tooltip": "每分钟请求数限制（RPM）。默认1000，根据您的API级别调整"
                }),
            }
        }

    RETURN_TYPES = ("LIST",)  # ✅ 输出类型为列表
    RETURN_NAMES = ("tags_list",)
    FUNCTION = "tag_all_images"
    CATEGORY = "MIKKY nodes/SiliconFlow"
    DESCRIPTION = "Send images to SiliconFlow Qwen3-VL with true async concurrency and rate limiting (RPM/TPM). Returns list of tags."

    # ----------------------------------------------------------
    # 工具函数：Tensor → base64 PNG
    # ----------------------------------------------------------
    def tensor_to_base64_png(self, image_tensor: torch.Tensor) -> str:
        """Convert ComfyUI IMAGE tensor to base64 PNG string."""
        img_array = torch.clamp(image_tensor * 255, 0, 255).cpu().numpy().astype(np.uint8)
        pil_img = Image.fromarray(img_array)
        buffer = io.BytesIO()
        pil_img.save(buffer, format="PNG", optimize=True)
        img_bytes = buffer.getvalue()
        base64_str = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:image/png;base64,{base64_str}"

    # ----------------------------------------------------------
    # 异步 API 调用函数
    # ----------------------------------------------------------
    async def call_vision_api(
        self,
        idx: int,
        base64_image: str,
        system_prompt: str,
        user_instruction: str,
        api_token: str,
        timeout: int,
        session: aiohttp.ClientSession
    ) -> tuple:
        """真正的异步请求函数"""
        url = "https://api.siliconflow.cn/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_token.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "messages": []
        }

        if system_prompt.strip():
            payload["messages"].append({"role": "system", "content": system_prompt.strip()})

        payload["messages"].append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_instruction.strip()},
                {"type": "image_url", "image_url": {"url": base64_image}}
            ]
        })

        start_time = time.time()
        try:
            async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    print(f"[✓] Completed image {idx + 1} in {time.time() - start_time:.2f}s")
                    return idx, content
                else:
                    text = await resp.text()
                    print(f"[✗] API ERROR {resp.status} on image {idx + 1}")
                    return idx, f"[API ERROR {resp.status}] {text}"
        except Exception as e:
            print(f"[!] Failed image {idx + 1}: {e}")
            return idx, f"[FAILED] {str(e)}"


    # ----------------------------------------------------------
    # 主函数：ComfyUI 调用接口
    # ----------------------------------------------------------
    def tag_all_images(
        self,
        images: torch.Tensor,
        system_prompt: str,
        user_instruction: str,
        api_token: str,
        max_concurrent: int,
        timeout: int,
        rpm_limit: int
    ) -> Tuple[List[str]]:

        if not api_token.strip():
            raise ValueError("API token is required.")
        if len(images) == 0:
            return ([],)

        total = len(images)
        
        # 创建速率限制器
        rate_limiter = RateLimiter(rpm_limit=rpm_limit, tpm_limit=10000)
        
        print(f"[MIKKY SiliconFlow Async Tagger] Processing {total} images with up to {max_concurrent} concurrent requests...")
        print(f"  - Timeout: {timeout}s")
        print(f"  - RPM limit: {rpm_limit} (≈{rpm_limit/60:.2f} req/s)")

        # Step 1: 图片转 base64
        base64_images = []
        for i, img in enumerate(images):
            print(f"  Encoding image {i + 1}/{total}...")
            base64_images.append(self.tensor_to_base64_png(img))

        # Step 2: 异步执行
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(self.async_tag_images(
            base64_images,
            system_prompt,
            user_instruction,
            api_token,
            max_concurrent,
            timeout,
            rate_limiter
        ))

        # ✅ Step 3: 返回 list（而非拼接字符串）
        print("[MIKKY SiliconFlow Async Tagger] All done!")
        return (results,)

    # ----------------------------------------------------------
    # 异步调度器（控制并发 + 速率限制）
    # ----------------------------------------------------------
    async def async_tag_images(
        self,
        base64_images,
        system_prompt,
        user_instruction,
        api_token,
        max_concurrent,
        timeout,
        rate_limiter: RateLimiter
    ) -> List[str]:
        """异步调度器，控制最大并发数量和请求速率"""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = [None] * len(base64_images)

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:

            async def sem_task(i, img):
                # 先获取速率限制令牌（在信号量外，允许并发获取）
                await rate_limiter.acquire()
                # 然后获取信号量（控制并发数）
                async with semaphore:
                    idx, res = await self.call_vision_api(
                        i, img, system_prompt, user_instruction, api_token, timeout, session
                    )
                    results[idx] = res

            tasks = [sem_task(i, img) for i, img in enumerate(base64_images)]
            await asyncio.gather(*tasks)

        return results


# 注册节点（ComfyUI）
NODE_CLASS_MAPPINGS = {
    "MIKKYSiliconFlowAsyncTagger": MIKKYSiliconFlowAsyncTagger,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYSiliconFlowAsyncTagger": "MIKKY SiliconFlow Async Tagger",
}

