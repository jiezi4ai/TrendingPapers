import numpy as np
from typing import List, Dict, Optional
from TrendingPapers.trendingpapers.models.default_models import ollama_embedding, semantic_similarity_matrix

async def filter_by_topics(
        benchmarks: List[str],  # list of strings (like keywords, titles, abstracts)
        candidates: List[str],  # list of strings (like keywords, titles, abstracts)
        threshold: Optional[float] = 0.7, 
        top_k: Optional[int] = 10):
    """based on user's preference match candidates papers' abstract to existing benchmark papers'
    Args:
        benchmarks: a list of keywords, titles, or abstracts of existing papers
        candidate_metadata: list of OAI metadata
    Returns:
        list of paper metadata after filter the non-matches
        list of matching information
    """
    # calculate the similarity matrix
    benchmarks_embeds = await ollama_embedding(benchmarks)
    candidates_embeds = await ollama_embedding(candidates)
    similarity_matrix = semantic_similarity_matrix(benchmarks_embeds, candidates_embeds)
    similarity_matrix = np.array(similarity_matrix)

    filtered_candidates, match_results = [], []
    _, num_cols = similarity_matrix.shape
    for j in range(num_cols):
        column = similarity_matrix[:, j]
        # find values and corresponding positions given threshold
        above_threshold_indices = np.where(column > threshold)[0]
        above_threshold_values = column[above_threshold_indices]

        if len(above_threshold_values) == 0:  # skip 
            continue
        sorted_indices = np.argsort(above_threshold_values)[::-1]  # desceding order
        selected_indices = sorted_indices[:3]

        matched_info = []
        for i in selected_indices:
          row_index = above_threshold_indices[i]
          similarity = above_threshold_values[i]
          matched_info.append({"row_index": row_index, "similarity": similarity.item()})
        opt = {"candidate_index": j, "matched_info": matched_info}
        match_results.append(opt)
        filtered_candidates.append(candidates[j])
    return filtered_candidates[0:top_k], match_results[0:top_k]