/**
 * Fuzzy Search Utility
 * 
 * Implements fuzzy string matching with typo tolerance,
 * multi-field search, and relevance scoring.
 */

// ─── Types ──────────────────────────────────────────────────────────────────

export interface SearchResult<T> {
  item: T;
  score: number;
  matchedFields: string[];
}

export interface SearchSuggestion {
  type: "history" | "topic" | "tag" | "skill" | "resource" | "field";
  label: string;
  value: string;
  icon?: string;
  count?: number;
}

// ─── Levenshtein Distance ────────────────────────────────────────────────────

/**
 * Calculate the Levenshtein distance between two strings.
 * This measures the number of edits (insert, delete, substitute) needed
 * to transform one string into another.
 */
export function levenshteinDistance(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  
  if (m === 0) return n;
  if (n === 0) return m;
  
  const dp: number[][] = Array(m + 1)
    .fill(null)
    .map(() => Array(n + 1).fill(0));
  
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1, // deletion
        dp[i][j - 1] + 1, // insertion
        dp[i - 1][j - 1] + cost // substitution
      );
    }
  }
  
  return dp[m][n];
}

// ─── Fuzzy Match ─────────────────────────────────────────────────────────────

/**
 * Check if a query fuzzy matches a text and return a score.
 * Higher score = better match.
 */
export function fuzzyMatch(query: string, text: string): number {
  if (!query || !text) return 0;
  
  const queryLower = query.toLowerCase().trim();
  const textLower = text.toLowerCase().trim();
  
  if (!queryLower || !textLower) return 0;
  
  // Exact match
  if (queryLower === textLower) return 100;
  
  // Starts with query
  if (textLower.startsWith(queryLower)) return 90;
  
  // Contains query as a whole word
  const textWords = textLower.split(/\s+/);
  if (textWords.includes(queryLower)) return 80;
  
  // Contains query as substring
  if (textLower.includes(queryLower)) return 70;
  
  // Token-based matching (each query token must match somewhere)
  const queryTokens = queryLower.split(/\s+/);
  let tokenScore = 0;
  let matchedTokens = 0;
  
  for (const token of queryTokens) {
    if (token.length < 2) continue;
    
    // Check if any word in text starts with this token
    const startsWithToken = textWords.some((w) => w.startsWith(token));
    if (startsWithToken) {
      tokenScore += 60;
      matchedTokens++;
      continue;
    }
    
    // Check if any word contains this token
    const containsToken = textWords.some((w) => w.includes(token));
    if (containsToken) {
      tokenScore += 50;
      matchedTokens++;
      continue;
    }
    
    // Fuzzy match against each word (typo tolerance)
    let bestFuzzyScore = 0;
    for (const word of textWords) {
      if (word.length < 3) continue;
      const distance = levenshteinDistance(token, word);
      const maxLength = Math.max(token.length, word.length);
      const similarity = 1 - distance / maxLength;
      
      // Only count as a match if similarity is high enough (> 0.7)
      if (similarity > 0.7) {
        const score = Math.round(similarity * 40);
        if (score > bestFuzzyScore) bestFuzzyScore = score;
      }
    }
    
    if (bestFuzzyScore > 0) {
      tokenScore += bestFuzzyScore;
      matchedTokens++;
    }
  }
  
  // Only return token score if all tokens matched
  if (matchedTokens === queryTokens.filter((t) => t.length >= 2).length && matchedTokens > 0) {
    return tokenScore;
  }
  
  return 0;
}

// ─── Search Query Parser ─────────────────────────────────────────────────────

export interface ParsedQuery {
  text: string;
  fields: Record<string, string>;
}

/**
 * Parse a search query that may contain field-specific syntax.
 * Examples:
 *   "reading comprehension" -> { text: "reading comprehension", fields: {} }
 *   "band:7 reading" -> { text: "reading", fields: { band: "7" } }
 *   "skill:reading type:video" -> { text: "", fields: { skill: "reading", type: "video" } }
 */
export function parseSearchQuery(query: string): ParsedQuery {
  const fields: Record<string, string> = {};
  const textParts: string[] = [];
  
  const tokens = query.trim().split(/\s+/);
  
  for (const token of tokens) {
    const colonIndex = token.indexOf(":");
    if (colonIndex > 0) {
      const field = token.substring(0, colonIndex).toLowerCase();
      const value = token.substring(colonIndex + 1);
      if (field && value) {
        fields[field] = value;
      }
    } else {
      textParts.push(token);
    }
  }
  
  return {
    text: textParts.join(" "),
    fields,
  };
}

// ─── Resource Search ─────────────────────────────────────────────────────────

/**
 * Get all searchable text from a resource item.
 */
function getSearchableFields(resource: any): Record<string, string> {
  return {
    title: resource.title || "",
    description: resource.description || "",
    skill: resource.skill || "",
    sub_skill: resource.sub_skill || "",
    type: resource.type || "",
    source: resource.source || "",
    author: resource.author || "",
    difficulty: resource.difficulty || "",
    tags: (resource.tags || []).join(" "),
    band: `${resource.minimum_band || ""} ${resource.maximum_band || ""}`.trim(),
    duration: resource.estimated_time ? `${resource.estimated_time}` : "",
  };
}

/**
 * Field weights - title matches rank higher than description matches
 */
const FIELD_WEIGHTS: Record<string, number> = {
  title: 3.0,
  skill: 2.5,
  sub_skill: 2.0,
  tags: 2.0,
  type: 1.5,
  source: 1.5,
  author: 1.5,
  difficulty: 1.0,
  description: 1.0,
  band: 1.0,
  duration: 0.5,
};

/**
 * Search resources using fuzzy matching across all fields.
 */
export function searchResources<T extends Record<string, any>>(
  resources: T[],
  query: string,
  options?: { limit?: number; minScore?: number }
): SearchResult<T>[] {
  if (!query || query.trim().length === 0) {
    return [];
  }
  
  const { limit = 20, minScore = 10 } = options || {};
  const parsed = parseSearchQuery(query);
  const results: SearchResult<T>[] = [];
  
  for (const resource of resources) {
    const fields = getSearchableFields(resource);
    let totalScore = 0;
    const matchedFields: string[] = [];
    
    // Handle field-specific queries
    for (const [field, value] of Object.entries(parsed.fields)) {
      const fieldValue = fields[field] || "";
      if (fieldValue) {
        const score = fuzzyMatch(value, fieldValue) * (FIELD_WEIGHTS[field] || 1.0);
        if (score > 0) {
          totalScore += score;
          if (!matchedFields.includes(field)) matchedFields.push(field);
        }
      }
    }
    
    // Handle free-text query
    if (parsed.text) {
      for (const [field, value] of Object.entries(fields)) {
        if (!value) continue;
        const score = fuzzyMatch(parsed.text, value) * (FIELD_WEIGHTS[field] || 1.0);
        if (score > 0) {
          totalScore += score;
          if (!matchedFields.includes(field)) matchedFields.push(field);
        }
      }
    }
    
    if (totalScore >= minScore) {
      results.push({
        item: resource,
        score: totalScore,
        matchedFields,
      });
    }
  }
  
  // Sort by score descending
  results.sort((a, b) => b.score - a.score);
  
  // Return top N results
  return results.slice(0, limit);
}

// ─── Search Suggestions ──────────────────────────────────────────────────────

/**
 * Generate search suggestions based on the current query and resources.
 */
export function generateSuggestions<T extends Record<string, any>>(
  resources: T[],
  query: string,
  history: string[],
  options?: { limit?: number }
): SearchSuggestion[] {
  const { limit = 8 } = options || {};
  const suggestions: SearchSuggestion[] = [];
  const seen = new Set<string>();
  
  // If query is empty, show history and popular topics
  if (!query || query.trim().length === 0) {
    // Show recent searches
    for (const item of history.slice(0, 4)) {
      if (!seen.has(item)) {
        seen.add(item);
        suggestions.push({
          type: "history",
          label: item,
          value: item,
          icon: "history",
        });
      }
    }
    
    // Show popular skills
    const skillCounts: Record<string, number> = {};
    for (const r of resources) {
      if (r.skill) {
        skillCounts[r.skill] = (skillCounts[r.skill] || 0) + 1;
      }
    }
    const topSkills = Object.entries(skillCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);
    for (const [skill, count] of topSkills) {
      if (!seen.has(skill)) {
        seen.add(skill);
        suggestions.push({
          type: "skill",
          label: skill,
          value: `skill:${skill.toLowerCase()}`,
          icon: "skill",
          count,
        });
      }
    }
    
    return suggestions.slice(0, limit);
  }
  
  const queryLower = query.toLowerCase().trim();
  
  // Check if query looks like a field search (contains ":")
  if (queryLower.includes(":")) {
    // Suggest field values
    const parsed = parseSearchQuery(query);
    for (const [field, value] of Object.entries(parsed.fields)) {
      const fieldValues = new Set<string>();
      for (const r of resources) {
        const fields = getSearchableFields(r);
        if (fields[field]) {
          fieldValues.add(fields[field]);
        }
      }
      for (const fv of fieldValues) {
        if (fuzzyMatch(value, fv) > 30 && !seen.has(fv)) {
          seen.add(fv);
          suggestions.push({
            type: "field",
            label: `${field}: ${fv}`,
            value: `${field}:${fv.toLowerCase()}`,
            icon: "field",
          });
        }
      }
    }
  }
  
  // Suggest matching skills
  const skills = new Set<string>();
  for (const r of resources) {
    if (r.skill) skills.add(r.skill);
  }
  for (const skill of skills) {
    if (fuzzyMatch(queryLower, skill.toLowerCase()) > 30 && !seen.has(skill)) {
      seen.add(skill);
      suggestions.push({
        type: "skill",
        label: skill,
        value: skill,
        icon: "skill",
      });
    }
  }
  
  // Suggest matching tags
  const tagCounts: Record<string, number> = {};
  for (const r of resources) {
    for (const tag of r.tags || []) {
      tagCounts[tag] = (tagCounts[tag] || 0) + 1;
    }
  }
  const topTags = Object.entries(tagCounts)
    .filter(([tag]) => fuzzyMatch(queryLower, tag.toLowerCase()) > 30)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
  for (const [tag, count] of topTags) {
    if (!seen.has(tag)) {
      seen.add(tag);
      suggestions.push({
        type: "tag",
        label: tag,
        value: tag,
        icon: "tag",
        count,
      });
    }
  }
  
  // Suggest matching resource titles
  const matchingResources = searchResources(resources, query, { limit: 3, minScore: 30 });
  for (const result of matchingResources) {
    const title = result.item.title;
    if (!seen.has(title)) {
      seen.add(title);
      suggestions.push({
        type: "resource",
        label: title,
        value: title,
        icon: "resource",
      });
    }
  }
  
  return suggestions.slice(0, limit);
}

// ─── Search History ──────────────────────────────────────────────────────────

const SEARCH_HISTORY_KEY = "ielts_resource_search_history";
const MAX_HISTORY_ITEMS = 10;

/**
 * Get search history from localStorage.
 */
export function getSearchHistory(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(SEARCH_HISTORY_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

/**
 * Add a search query to history.
 */
export function addToSearchHistory(query: string): void {
  if (typeof window === "undefined") return;
  if (!query || query.trim().length === 0) return;
  
  try {
    const history = getSearchHistory();
    const queryTrimmed = query.trim();
    
    // Remove if already exists (move to top)
    const filtered = history.filter((h) => h !== queryTrimmed);
    
    // Add to front
    filtered.unshift(queryTrimmed);
    
    // Keep only last N items
    const trimmed = filtered.slice(0, MAX_HISTORY_ITEMS);
    
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(trimmed));
  } catch {
    // Silently fail
  }
}

/**
 * Clear search history.
 */
export function clearSearchHistory(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(SEARCH_HISTORY_KEY);
  } catch {
    // Silently fail
  }
}

/**
 * Remove a single item from search history.
 */
export function removeFromSearchHistory(query: string): void {
  if (typeof window === "undefined") return;
  try {
    const history = getSearchHistory();
    const filtered = history.filter((h) => h !== query);
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(filtered));
  } catch {
    // Silently fail
  }
}