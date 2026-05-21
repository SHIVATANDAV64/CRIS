export interface Decomposition {
  literature_queries: string[];
  hypothesis_candidates: string[];
  method_analysis_targets: string[];
  cross_domain_pairs: Array<{ source: string; target: string; rationale: string }>;
}

export interface CrossDomainConnection {
  id: string;
  title: string;
  domain: string;
  similarity: number;
  abstract: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  thinking?: string;
  sources?: Source[];
  decomposition?: Decomposition;
  timestamp: number;
}

export interface Source {
  arxiv_id: string;
  title: string;
  contribution_type?: string;
  domains?: string;
  url?: string;
}

export interface Session {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  description: string;
}

export interface Paper {
  arxiv_id: string;
  title: string;
  authors?: string[];
  categories?: string;
  created?: string;
  abstract?: string;
  fetched_at?: string;
}

export interface DateGroup {
  date: string;
  paper_count: number;
  categories: CategoryGroup[];
}

export interface CategoryGroup {
  category: string;
  display_name: string;
  paper_count: number;
  papers: Paper[];
}

export interface WikiStats {
  sources: number;
  concepts: number;
  entities: number;
  notes: number;
  last_updated: string;
}

export interface Entity {
  name: string;
  type: string;
  mentions: number;
  first_seen: string;
}

export interface Note {
  title: string;
  date: string;
  session_id: string;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}
