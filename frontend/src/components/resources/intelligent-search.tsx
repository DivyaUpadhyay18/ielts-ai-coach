"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Search,
  X,
  Clock,
  Tag,
  BookOpen,
  FileText,
  Hash,
  ChevronRight,
  Trash2,
  Sparkles,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  generateSuggestions,
  getSearchHistory,
  addToSearchHistory,
  clearSearchHistory,
  removeFromSearchHistory,
  searchResources,
  type SearchSuggestion,
} from "@/lib/fuzzy-search";
import type { ResourceItem } from "@/types";

interface IntelligentSearchProps {
  resources: ResourceItem[];
  onSearch: (query: string, results: ResourceItem[]) => void;
  onClear: () => void;
  placeholder?: string;
  className?: string;
}

const SUGGESTION_ICONS: Record<string, React.ElementType> = {
  history: Clock,
  topic: BookOpen,
  tag: Hash,
  skill: BookOpen,
  resource: FileText,
  field: Tag,
};

const SUGGESTION_COLORS: Record<string, string> = {
  history: "text-blue-500",
  topic: "text-purple-500",
  tag: "text-amber-500",
  skill: "text-green-500",
  resource: "text-indigo-500",
  field: "text-teal-500",
};

const SUGGESTION_LABELS: Record<string, string> = {
  history: "Recent",
  topic: "Topic",
  tag: "Tag",
  skill: "Skill",
  resource: "Resource",
  field: "Field",
};

export function IntelligentSearch({
  resources,
  onSearch,
  onClear,
  placeholder = "Search by keyword, topic, band, skill, tags... (e.g. 'reading band:7')",
  className = "",
}: IntelligentSearchProps) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [isFocused, setIsFocused] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // ─── Load search history on mount ───
  useEffect(() => {
    setHistory(getSearchHistory());
  }, []);

  // ─── Debounce search query ───
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 200);
    return () => clearTimeout(timer);
  }, [query]);

  // ─── Generate suggestions ───
  useEffect(() => {
    if (!isFocused) {
      setSuggestions([]);
      return;
    }
    const newSuggestions = generateSuggestions(resources, debouncedQuery, history, { limit: 8 });
    setSuggestions(newSuggestions);
    setActiveSuggestion(-1);
  }, [debouncedQuery, history, resources, isFocused]);

  // ─── Handle search execution ───
  const executeSearch = useCallback(
    (searchQuery: string) => {
      if (!searchQuery || searchQuery.trim().length === 0) {
        onClear();
        return;
      }

      // Add to history
      addToSearchHistory(searchQuery);
      setHistory(getSearchHistory());

      // Perform fuzzy search on resources
      const results = searchResources(resources, searchQuery, { limit: 999, minScore: 10 });
      const matchedResources = results.map((r) => r.item);

      onSearch(searchQuery, matchedResources);
      setShowSuggestions(false);
      inputRef.current?.blur();
    },
    [resources, onSearch, onClear]
  );

  // ─── Handle input change ───
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    setShowSuggestions(true);
    if (e.target.value === "") {
      onClear();
    }
  };

  // ─── Handle suggestion click ───
  const handleSuggestionClick = (suggestion: SearchSuggestion) => {
    setQuery(suggestion.value);
    executeSearch(suggestion.value);
  };

  // ─── Handle clear ───
  const handleClear = () => {
    setQuery("");
    setDebouncedQuery("");
    onClear();
    inputRef.current?.focus();
  };

  // ─── Handle keyboard navigation ───
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === "Enter" && query) {
        executeSearch(query);
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveSuggestion((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveSuggestion((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
        break;
      case "Enter":
        e.preventDefault();
        if (activeSuggestion >= 0 && activeSuggestion < suggestions.length) {
          handleSuggestionClick(suggestions[activeSuggestion]);
        } else if (query) {
          executeSearch(query);
        }
        break;
      case "Escape":
        e.preventDefault();
        setShowSuggestions(false);
        inputRef.current?.blur();
        break;
      case "Tab":
        if (activeSuggestion >= 0 && activeSuggestion < suggestions.length) {
          e.preventDefault();
          handleSuggestionClick(suggestions[activeSuggestion]);
        }
        break;
    }
  };

  // ─── Handle focus ───
  const handleFocus = () => {
    setIsFocused(true);
    setShowSuggestions(true);
  };

  // ─── Handle blur (with delay to allow click on suggestions) ───
  const handleBlur = () => {
    setIsFocused(false);
    setTimeout(() => {
      setShowSuggestions(false);
    }, 200);
  };

  // ─── Handle clear history ───
  const handleClearHistory = (e: React.MouseEvent) => {
    e.stopPropagation();
    clearSearchHistory();
    setHistory([]);
  };

  // ─── Handle remove history item ───
  const handleRemoveHistoryItem = (e: React.MouseEvent, item: string) => {
    e.stopPropagation();
    removeFromSearchHistory(item);
    setHistory(getSearchHistory());
  };

  // ─── Scroll active suggestion into view ───
  useEffect(() => {
    if (activeSuggestion >= 0 && suggestionsRef.current) {
      const activeElement = suggestionsRef.current.children[activeSuggestion] as HTMLElement;
      if (activeElement) {
        activeElement.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  }, [activeSuggestion]);

  // ─── Check if query has field syntax ───
  const hasFieldSyntax = useMemo(() => query.includes(":"), [query]);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Search Input */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={placeholder}
          className="pl-12 h-14 text-base rounded-xl shadow-sm focus:ring-2 focus:ring-primary/20 transition-all"
          aria-label="Search resources"
          aria-expanded={showSuggestions}
          aria-autocomplete="list"
          role="combobox"
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Clear search"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Suggestions Dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute z-50 mt-2 w-full rounded-xl border border-border bg-card shadow-xl overflow-hidden animate-slide-down max-h-96 overflow-y-auto scrollbar-thin"
          role="listbox"
        >
          {/* Header with clear history (only when showing history) */}
          {suggestions.some((s) => s.type === "history") && (
            <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Suggestions
              </span>
              <button
                onClick={handleClearHistory}
                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
              >
                <Trash2 className="h-3 w-3" />
                Clear history
              </button>
            </div>
          )}

          {/* Suggestion items */}
          {suggestions.map((suggestion, index) => {
            const Icon = SUGGESTION_ICONS[suggestion.type] || Search;
            const color = SUGGESTION_COLORS[suggestion.type] || "text-muted-foreground";
            const label = SUGGESTION_LABELS[suggestion.type] || "";
            const isActive = index === activeSuggestion;

            return (
              <button
                key={`${suggestion.type}-${suggestion.value}-${index}`}
                onClick={() => handleSuggestionClick(suggestion)}
                onMouseEnter={() => setActiveSuggestion(index)}
                className={`flex items-center gap-3 w-full px-4 py-2.5 text-left transition-colors ${
                  isActive ? "bg-primary/5 border-l-2 border-primary" : "border-l-2 border-transparent"
                } hover:bg-muted/50`}
                role="option"
                aria-selected={isActive}
              >
                {/* Icon */}
                <div className={`flex-shrink-0 ${color}`}>
                  <Icon className="h-4 w-4" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{suggestion.label}</span>
                    {suggestion.count !== undefined && (
                      <Badge variant="secondary" className="text-xs h-4 px-1.5">
                        {suggestion.count}
                      </Badge>
                    )}
                  </div>
                  {label && (
                    <span className="text-xs text-muted-foreground">{label}</span>
                  )}
                </div>

                {/* Action indicator */}
                {suggestion.type === "history" ? (
                  <button
                    onClick={(e) => handleRemoveHistoryItem(e, suggestion.value)}
                    className="flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Remove from history"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : (
                  <ChevronRight className="flex-shrink-0 h-4 w-4 text-muted-foreground" />
                )}
              </button>
            );
          })}

          {/* Footer with search tips */}
          <div className="border-t border-border bg-muted/30 px-4 py-2">
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="h-3 w-3" />
              <span>
                Try: <code className="text-primary font-medium">band:7</code>,{" "}
                <code className="text-primary font-medium">skill:reading</code>,{" "}
                <code className="text-primary font-medium">type:video</code>
              </span>
            </p>
          </div>
        </div>
      )}

      {/* No results message when focused but no suggestions */}
      {showSuggestions && isFocused && debouncedQuery && suggestions.length === 0 && (
        <div className="absolute z-50 mt-2 w-full rounded-xl border border-border bg-card shadow-xl overflow-hidden animate-slide-down">
          <div className="px-4 py-6 text-center">
            <Search className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium">No suggestions found</p>
            <p className="text-xs text-muted-foreground mt-1">
              Press <kbd className="px-1.5 py-0.5 rounded border border-border text-xs">Enter</kbd> to search for {`"${debouncedQuery}"`}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}