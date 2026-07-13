from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    total_results: int
    current_page: int
    total_pages: int
    per_page: int
    results: list[T]
