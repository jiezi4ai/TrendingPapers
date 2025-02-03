import ollama
import numpy as np

async def ollama_embedding(model, texts :list[str]) -> np.ndarray:
    embed_text = []
    for text in texts:
      data = ollama.embeddings(model=model, prompt=text)
      embed_text.append(data["embedding"])
    return embed_text

from sentence_transformers import util

def semantic_similarity_matrix(vec_x, vec_y):
    # embeds = await ollama_embedding(text_lst)
    cosine_scores = util.pytorch_cos_sim(vec_x, vec_y)  # 计算余弦相似度矩阵，仅计算上三角部分
    return cosine_scores

from google import genai
from google.genai import types

def gemini_llm(api_key, model_name, qa_prompt, sys_prompt=None, temperature=0.3):
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        temperature=temperature)
    response = client.models.generate_content(
        model=model_name, 
        contents=qa_prompt,
        config=config)
    return response.text

