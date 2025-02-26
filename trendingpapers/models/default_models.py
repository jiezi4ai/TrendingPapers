import math
import time
import asyncio
import numpy as np
from typing import List
from sentence_transformers import util  # pip install sentence-transformers https://github.com/UKPLab/sentence-transformers

import ollama  # pip install ollama
from google import genai  # pip install google-genai https://github.com/googleapis/python-genai
from google.genai import types  


async def ollama_embedding(model, texts :list[str]) -> np.ndarray:
    embed_text = []
    for text in texts:
      data = ollama.embeddings(model=model, prompt=text)
      embed_text.append(data["embedding"])
    return embed_text

def gemini_llm(api_key, model_name, qa_prompt, sys_prompt=None, temperature=0.3):
    """gemini llm generation"""
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        temperature=temperature)
    response = client.models.generate_content(
        model=model_name, 
        contents=qa_prompt,
        config=config)
    return response.text

def gemini_embedding_sync(api_key, model_name, texts: List[str]) -> np.ndarray:
    """gemeni text embedding"""
    client = genai.Client(api_key=api_key)
    n = math.ceil(len(texts) / 100)

    embeddings = []
    for i in range(n):
        texts_btch = texts[i*100: i*100+100]
        btch_result = client.models.embed_content(
            model=model_name,  # "models/text-embedding-004",
            contents=texts_btch)
        btch_embeddings = btch_result.to_json_dict()['embeddings']
        embeddings.extend([item['values'] for item in btch_embeddings])
        time.sleep(5)
    return np.array(embeddings)

async def _batch_embedding_async(api_key, model_name, texts_btch, semaphore):
    """异步处理单个批次的文本嵌入 (使用 asyncio.to_thread 包装同步调用)"""
    async with semaphore: # 获取信号量，限制并发数
        client = genai.Client(api_key=api_key)
        loop = asyncio.get_running_loop() # 获取当前事件循环
        btch_result = await loop.run_in_executor(None, # 使用默认的 ThreadPoolExecutor
                                                lambda: client.models.embed_content( # lambda 包装同步调用
                                                    model=model_name,
                                                    contents=texts_btch))
        btch_embeddings = btch_result.to_json_dict()['embeddings']
        embeddings = [item['values'] for item in btch_embeddings]
        await asyncio.sleep(5) # 异步 sleep，不阻塞线程
        return embeddings

async def gemini_embedding_async(api_key, model_name, texts: List[str], n_concurrent: int) -> np.ndarray:
    """并发执行的 gemini 文本嵌入"""
    n = math.ceil(len(texts) / 100)
    semaphore = asyncio.Semaphore(n_concurrent) # 创建信号量，限制并发数
    tasks = []
    all_embeddings = []

    for i in range(n):
        texts_btch = texts[i*100: i*100+100]
        task = asyncio.create_task(_batch_embedding_async(api_key, model_name, texts_btch, semaphore))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True) # 并发执行所有任务，并捕获异常

    for result in results:
        if isinstance(result, Exception):
            print(f"子任务发生异常: {result}") # 打印异常信息，可以根据需要进行更详细的错误处理
            # 决定如何处理异常，例如：跳过当前批次，记录错误日志等
        else:
            all_embeddings.extend(result) # 汇总正常批次的结果

    return np.array(all_embeddings)

def semantic_similarity_matrix(vec_x, vec_y):
    # embeds = await ollama_embedding(text_lst)
    cosine_scores = util.pytorch_cos_sim(vec_x, vec_y)  # 计算余弦相似度矩阵，仅计算上三角部分
    return cosine_scores