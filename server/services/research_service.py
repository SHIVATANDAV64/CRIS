"""
Research Engine Core Service — Phase 2 Implementation

Provides:
- ResearchDecomposer: Breaks research questions into sub-queries
- CrossDomainMapper: Finds papers from different fields with semantic similarity
- EvidenceSynthesizer: Aggregates findings, resolves contradictions
"""

import uuid
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from core.model_client import ModelClient
from core.search_engine import search
from core.web_tools import get_search
from config.settings import SEARXNG_MODAL_URL


@dataclass
class DecompositionResult:
    """Output of ResearchDecomposer."""
    id: str
    original_query: str
    depth: str
    literature_queries: List[str]
    hypothesis_candidates: List[str]
    method_analysis_targets: List[str]
    cross_domain_pairs: List[Dict[str, str]]
    sub_query_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CrossDomainConnection:
    """A found connection between papers from different domains."""
    source_paper_id: str
    source_title: str
    source_domain: str
    target_paper_id: str
    target_title: str
    target_domain: str
    mechanism_analogy: str
    connection_strength: float  # 0-1


@dataclass
class SynthesizedFinding:
    """A synthesized finding with inline citations."""
    claim: str
    supporting_papers: List[str]
    confidence: float  # 0-1
    contradictions: List[str] = field(default_factory=list)
    evidence_summary: str = ""


class ResearchService:
    """Core Research Engine - decomposes, maps, synthesizes."""

    def __init__(self):
        self._model_clients: dict[str, ModelClient] = {}
        self._decompositions: dict[str, DecompositionResult] = {}

    def get_model_client(self, model_id: Optional[str] = None) -> Optional[ModelClient]:
        key = model_id or "darwin-opus"
        if key not in self._model_clients:
            try:
                self._model_clients[key] = ModelClient(model_id=model_id)
            except Exception as e:
                print(f"[research] Warning: Could not initialize model client ({key}): {e}")
                return None
        return self._model_clients.get(key)

    # ─────────────────────────────────────────────────────────────────────────
    # Research Decomposer
    # ─────────────────────────────────────────────────────────────────────────

    DECOMPOSER_PROMPT = """You are a research decomposition expert. Given a research question, break it down into structured sub-queries that can be executed independently.

Analyze the question and produce:
1. LITERATURE_QUERIES: 2-4 specific search queries to find relevant prior work. Do NOT append past years (such as 2024 or earlier) to search queries unless explicitly requested by the user. Keep queries temporal-neutral or use the current year (2026) for recent topics.
2. HYPOTHESIS_CANDIDATES: 2-3 potential testable hypotheses implicit in the question
3. METHOD_ANALYSIS_TARGETS: Key methods/techniques to analyze
4. CROSS_DOMAIN_PAIRS: Pairs of domains that might have relevant connections (e.g., "neuroscience<->machine learning")

Return ONLY valid JSON in this exact format:
{{
  "literature_queries": ["query 1", "query 2"],
  "hypothesis_candidates": ["hypothesis 1", "hypothesis 2"],
  "method_analysis_targets": ["method 1", "method 2"],
  "cross_domain_pairs": [
    {{"source": "domain A", "target": "domain B", "rationale": "why these might connect"}}
  ]
}}

Research question to decompose: {query}"""

    async def decompose(self, query: str, depth: str = "shallow", model_id: Optional[str] = None) -> DecompositionResult:
        """Decompose a research question into sub-queries."""
        decomposition_id = str(uuid.uuid4())

        client = self.get_model_client(model_id)
        if not client:
            # Fallback: simple keyword-based decomposition
            return self._fallback_decompose(query, decomposition_id, depth)

        try:
            result = client.generate(
                user_message=self.DECOMPOSER_PROMPT.format(query=query),
                system_prompt="You are a research decomposition expert. Return ONLY valid JSON.",
            )
            response = result.get("response", "{}").strip()

            # Extract JSON
            import re
            json_match = re.search(r'\{.+}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = {}

            decomposition = DecompositionResult(
                id=decomposition_id,
                original_query=query,
                depth=depth,
                literature_queries=data.get("literature_queries", [query]),
                hypothesis_candidates=data.get("hypothesis_candidates", []),
                method_analysis_targets=data.get("method_analysis_targets", []),
                cross_domain_pairs=data.get("cross_domain_pairs", []),
            )
        except Exception as e:
            print(f"[research] Decomposition failed: {e}")
            decomposition = self._fallback_decompose(query, decomposition_id, depth)

        self._decompositions[decomposition_id] = decomposition
        return decomposition

    def _fallback_decompose(self, query: str, decomposition_id: str, depth: str) -> DecompositionResult:
        """Fallback decomposition using simple keyword extraction."""
        keywords = [w for w in query.split() if len(w) > 3]
        return DecompositionResult(
            id=decomposition_id,
            original_query=query,
            depth=depth,
            literature_queries=[query],
            hypothesis_candidates=[],
            method_analysis_targets=keywords[:5],
            cross_domain_pairs=[],
        )

    async def execute_decomposition(self, decomposition_id: str, model_id: Optional[str] = None) -> DecompositionResult:
        """Execute all sub-queries from a decomposition."""
        decomposition = self._decompositions.get(decomposition_id)
        if not decomposition:
            raise ValueError(f"Decomposition {decomposition_id} not found")

        all_results = []

        # Execute literature queries in parallel
        for query in decomposition.literature_queries[:5]:
            results = search(query, limit=10)
            all_results.append({
                "query": query,
                "results": results,
            })

            # Also search web if configured
            if SEARXNG_MODAL_URL:
                try:
                    web_search = get_search(SEARXNG_MODAL_URL)
                    web_results = await web_search.search(query, num_results=5)
                    all_results.append({
                        "query": query,
                        "results": [
                            {
                                "arxiv_id": r.get("url", "").split("/")[-1][:20],
                                "title": r.get("title", ""),
                                "contribution_type": "Web",
                                "domains": r.get("category", "web"),
                                "wiki_content": r.get("snippet", ""),
                            }
                            for r in web_results
                        ],
                    })
                except Exception as e:
                    print(f"[research] Web search failed for '{query}': {e}")

        decomposition.sub_query_results = all_results
        return decomposition

    # ─────────────────────────────────────────────────────────────────────────
    # Cross-Domain Mapper
    # ─────────────────────────────────────────────────────────────────────────

    CROSS_DOMAIN_PROMPT = """You are a cross-domain research mapper. Given a paper and target domains, find papers in those domains with analogous mechanisms.

Source paper: {title}
Source domain: {domain}
Abstract: {abstract}

Target domains to search: {targets}

For each target domain, find papers that share similar mechanisms, concepts, or approaches.
Return ONLY valid JSON:
{{
  "connections": [
    {{
      "target_paper_id": "paper id or URL",
      "target_title": "paper title",
      "target_domain": "domain name",
      "mechanism_analogy": "how the mechanisms are analogous",
      "connection_strength": 0.0-1.0
    }}
  ]
}}"""

    async def find_connections(
        self,
        paper_id: str,
        title: str,
        abstract: str,
        domain: str,
        target_domains: List[str],
        model_id: Optional[str] = None,
    ) -> List[CrossDomainConnection]:
        """Find cross-domain connections for a paper."""
        client = self.get_model_client(model_id)
        if not client:
            return []

        targets = ", ".join(target_domains)
        prompt = self.CROSS_DOMAIN_PROMPT.format(
            title=title,
            domain=domain,
            abstract=abstract[:1000],
            targets=targets,
        )

        try:
            result = client.generate(
                user_message=prompt,
                system_prompt="You are a cross-domain research mapper. Return ONLY valid JSON.",
            )
            response = result.get("response", "{}").strip()

            import re
            json_match = re.search(r'\{.+}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = {}

            connections = []
            for conn in data.get("connections", []):
                connections.append(CrossDomainConnection(
                    source_paper_id=paper_id,
                    source_title=title,
                    source_domain=domain,
                    target_paper_id=conn.get("target_paper_id", ""),
                    target_title=conn.get("target_title", ""),
                    target_domain=conn.get("target_domain", ""),
                    mechanism_analogy=conn.get("mechanism_analogy", ""),
                    connection_strength=conn.get("connection_strength", 0.5),
                ))
            return connections
        except Exception as e:
            print(f"[research] Cross-domain mapping failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Evidence Synthesizer
    # ─────────────────────────────────────────────────────────────────────────

    SYNTHESIZER_PROMPT = """You are an evidence synthesis expert. Given multiple research sources, synthesize findings into coherent claims with inline citations.

Research question: {question}

Sources (format: ID - Title - Content):
{sources}

TASK:
1. Identify key findings that answer the question
2. For each finding, cite the supporting sources
3. Note any contradictions between sources and explain why
4. Assign confidence scores based on evidence quality

Return ONLY valid JSON:
{{
  "findings": [
    {{
      "claim": "factual statement with inline citations",
      "supporting_papers": ["source 1", "source 2"],
      "confidence": 0.0-1.0,
      "contradictions": ["note if any sources disagree"],
      "evidence_summary": "summary of supporting evidence"
    }}
  ],
  "summary": "overall synthesis summary"
}}"""

    async def synthesize(
        self,
        question: str,
        sources: List[Dict[str, Any]],
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize findings from multiple sources."""
        client = self.get_model_client(model_id)
        if not client:
            return {"error": "Model client not available", "findings": []}

        # Format sources for prompt
        sources_text = ""
        for i, s in enumerate(sources[:20]):  # Limit to 20 sources
            content = s.get("wiki_content", s.get("abstract", ""))[:500]
            title = s.get("title", s.get("arxiv_id", "Unknown"))
            sources_text += f"\n{i+1}. [{s.get('arxiv_id', 'web')}] {title}\n{content}\n"

        prompt = self.SYNTHESIZER_PROMPT.format(question=question, sources=sources_text)

        try:
            result = client.generate(
                user_message=prompt,
                system_prompt="You are an evidence synthesis expert. Return ONLY valid JSON.",
            )
            response = result.get("response", "{}").strip()

            import re
            json_match = re.search(r'\{.+}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = {"findings": [], "summary": response}

            # Convert to SynthesizedFinding objects
            findings = []
            for f in data.get("findings", []):
                findings.append(SynthesizedFinding(
                    claim=f.get("claim", ""),
                    supporting_papers=f.get("supporting_papers", []),
                    confidence=f.get("confidence", 0.5),
                    contradictions=f.get("contradictions", []),
                    evidence_summary=f.get("evidence_summary", ""),
                ))

            return {
                "question": question,
                "findings": [asdict(f) for f in findings],
                "summary": data.get("summary", ""),
                "sources_used": len(sources),
            }
        except Exception as e:
            print(f"[research] Synthesis failed: {e}")
            return {"error": str(e), "findings": [], "question": question}


# Singleton instance
research_service = ResearchService()