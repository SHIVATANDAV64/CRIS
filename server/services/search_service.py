from typing import List, Dict, Any, Optional

from core.search_engine import search, get_stats, get_all_entries
from core.domain_manager import (
    get_domains,
    get_papers_for_domain,
    get_paper_detail,
    migrate_existing_papers,
    get_raw_sources as load_raw_sources,
    get_paper_by_id,
)


class SearchService:
    def __init__(self):
        pass

    def search_papers(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return search(query, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        return get_stats()

    def list_papers(self, limit: int = 50) -> List[Dict[str, Any]]:
        return get_all_entries()[:limit]

    def list_domains(self) -> List[Dict[str, Any]]:
        return get_domains()

    def get_domain_papers(self, domain: str) -> Dict[str, Any]:
        return get_papers_for_domain(domain)

    def get_paper_detail(self, domain: str, date: str, paper_id: str) -> Optional[Dict[str, Any]]:
        return get_paper_detail(domain, date, paper_id)

    def migrate_sources(self) -> Dict[str, int]:
        return migrate_existing_papers()

    def list_raw_sources(self) -> List[Dict[str, Any]]:
        return load_raw_sources()

    def get_raw_paper(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        return get_paper_by_id(arxiv_id)
