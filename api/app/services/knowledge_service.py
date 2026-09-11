import re
from collections.abc import Iterable
from typing import Any


def _words_from_text(text: str) -> set[str]:
    return {word for word in re.findall(r"[\wÀ-ÿ]+", text.lower()) if word}


def _keywords_from_article(article: dict[str, Any]) -> list[str]:
    raw_keywords = article.get("keywords", [])
    if isinstance(raw_keywords, list):
        return [str(keyword).strip().lower() for keyword in raw_keywords if str(keyword).strip()]
    return []


def list_articles(category: str | None, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if category is None:
        return [dict(article) for article in articles]
    normalized_category = category.strip().lower()
    return [dict(article) for article in articles if str(article.get("category", "")).strip().lower() == normalized_category]


def get_article(article_id: str, articles: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    normalized_article_id = article_id.strip().upper()
    return next((dict(article) for article in articles if str(article.get("id", "")).upper() == normalized_article_id), None)


def search_knowledge(query: str, category: str | None, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query_words = _words_from_text(query)
    filtered_articles = list_articles(category, articles)
    results: list[dict[str, Any]] = []
    normalized_category = category.strip().lower() if category else None

    for article in filtered_articles:
        keywords = _keywords_from_article(article)
        keyword_words = {word for keyword in keywords for word in _words_from_text(keyword)}
        if not keyword_words:
            continue

        matches = len(query_words & keyword_words)
        category_match = 1.0 if normalized_category and article["category"] == normalized_category else 0.0
        score = ((matches / len(keyword_words)) * 0.7) + (category_match * 0.3)

        if matches == 0 and category_match == 0.0:
            continue

        results.append(
            {
                "id": article["id"],
                "title": article["title"],
                "category": article["category"],
                "score": round(score, 4),
                "content": article["content"],
                "can_answer_automatically": article.get("can_answer_automatically", False),
                "requires_human": article.get("requires_human", False),
            }
        )

    return sorted(results, key=lambda item: item["score"], reverse=True)
