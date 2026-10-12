import React from 'react';
import { Search, Filter, RotateCcw } from 'lucide-react';

export default function FilterBar({ filters, onFilterChange, onReset }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs mb-6 space-y-3">
      
      {/* Search Input Row */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by Title, Author, Publisher, or ISBN..."
            value={filters.query_text || ''}
            onChange={(e) => onFilterChange('query_text', e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
          />
        </div>

        <button
          onClick={onReset}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 transition-colors shrink-0"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset Filters</span>
        </button>
      </div>

      {/* Dropdown Filters Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        
        {/* Category */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-500 mb-1">Category</label>
          <select
            value={filters.category || 'All'}
            onChange={(e) => onFilterChange('category', e.target.value)}
            className="w-full p-2 border border-slate-300 rounded-xl text-xs focus:ring-1 focus:ring-blue-500"
          >
            <option value="All">All Categories</option>
            <option value="Textbook">Textbooks Only</option>
            <option value="Reference Book">Reference Books Only</option>
          </select>
        </div>

        {/* Access Type */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-500 mb-1">Access Type</label>
          <select
            value={filters.access_type || 'All'}
            onChange={(e) => onFilterChange('access_type', e.target.value)}
            className="w-full p-2 border border-slate-300 rounded-xl text-xs focus:ring-1 focus:ring-blue-500"
          >
            <option value="All">All Access Types</option>
            <option value="Open Access">Verified Open Access</option>
            <option value="Public-domain">Public Domain</option>
            <option value="Preview / Borrowing">Preview / Borrowing</option>
            <option value="Borrowing available">Borrowing Available</option>
            <option value="Preview available">Preview Available</option>
            <option value="Catalogue / Publisher">Catalogue / Publisher</option>
            <option value="No Verified Access">No Verified Access</option>
          </select>
        </div>

        {/* Source */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-500 mb-1">Source</label>
          <select
            value={filters.source || 'All'}
            onChange={(e) => onFilterChange('source', e.target.value)}
            className="w-full p-2 border border-slate-300 rounded-xl text-xs focus:ring-1 focus:ring-blue-500"
          >
            <option value="All">All Repositories</option>
            <option value="Google Books">Google Books</option>
            <option value="Open Library">Open Library</option>
            <option value="Crossref">Crossref</option>
            <option value="DOAB">DOAB</option>
            <option value="WorldCat">WorldCat</option>
            <option value="Google Scholar">Google Scholar</option>
          </select>
        </div>

        {/* Confidence Minimum */}
        <div>
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 mb-1">
            <span>Min Confidence</span>
            <span className="text-blue-600 font-bold">{filters.min_confidence || 0}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="5"
            value={filters.min_confidence || 0}
            onChange={(e) => onFilterChange('min_confidence', parseFloat(e.target.value))}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600 mt-2"
          />
        </div>

      </div>

    </div>
  );
}
