from typing import List, Dict, Any

def rank_candidates(rows: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """按技术评分排序并返回前N个"""
    sorted_rows = sorted(rows, key=lambda row: row.get("technical_score", 0), reverse=True)
    return sorted_rows[:top_n]

def filter_by_volume(rows: List[Dict[str, Any]], min_volume: int = 10000) -> List[Dict[str, Any]]:
    """按成交量过滤"""
    return [row for row in rows if row.get("volume", 0) >= min_volume]