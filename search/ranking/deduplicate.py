from search.schemas import SearchResult


def remove_duplicates(
    results: list[SearchResult],
) -> list[SearchResult]:

    unique: dict[tuple, SearchResult] = {}

    for result in results:

        key = (
            result.type,
            result.id,
        )

        if key not in unique:
            unique[key] = result
            continue

        if result.score > unique[key].score:
            unique[key] = result

    return list(unique.values())