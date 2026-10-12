import React, { useState, useEffect } from 'react';
import { 
  Search, 
  RefreshCw, 
  Download, 
  BookOpen, 
  Filter, 
  ExternalLink, 
  CheckCircle2, 
  ShieldCheck,
  Sparkles,
  Zap,
  Check
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { useDebounce } from '../hooks/useDebounce';
import { api } from '../services/api';
import BookCard from '../components/BookCard';
import FilterBar from '../components/FilterBar';
import BookDiscoveryRAGPanel from '../components/BookDiscoveryRAGPanel';

export default function ResultsPage() {
  const { 
    currentSyllabus, 
    searchResults, 
    loadSearchResults, 
    runLawfulSearch, 
    setActiveTab, 
    loading,
    notify 
  } = useApp();

  const [autoDownloadOA, setAutoDownloadOA] = useState(false);
  const [isUpdatingSettings, setIsUpdatingSettings] = useState(false);

  const [filters, setFilters] = useState({
    category: 'All',
    access_type: 'All',
    source: 'All',
    min_confidence: 0,
    query_text: '',
  });

  const debouncedQuery = useDebounce(filters.query_text, 350);

  // Load faculty settings on mount
  useEffect(() => {
    api.getFacultySettings()
      .then(res => {
        if (res && res.auto_download_verified_oa !== undefined) {
          setAutoDownloadOA(Boolean(res.auto_download_verified_oa));
        }
      })
      .catch(err => {
        console.error('Could not load faculty settings:', err);
      });
  }, []);

  useEffect(() => {
    if (currentSyllabus) {
      loadSearchResults(currentSyllabus.id, {
        ...filters,
        query_text: debouncedQuery,
      });
    }
  }, [currentSyllabus, filters.category, filters.access_type, filters.source, filters.min_confidence, debouncedQuery]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleResetFilters = () => {
    setFilters({
      category: 'All',
      access_type: 'All',
      source: 'All',
      min_confidence: 0,
      query_text: '',
    });
  };

  const handleToggleAutoDownload = async () => {
    const nextVal = !autoDownloadOA;
    setAutoDownloadOA(nextVal);
    setIsUpdatingSettings(true);
    try {
      await api.updateFacultySettings({ auto_download_verified_oa: nextVal });
      if (nextVal) {
        notify('Setting enabled: Automatically download and index verified open-access books', 'success');
        if (currentSyllabus) {
          const res = await api.triggerAutoDownloadJobs(currentSyllabus.id);
          notify(res.message || 'Auto-download and indexing pipeline launched for verified books.', 'info');
        }
      } else {
        notify('Setting disabled: Automatic open-access download turned off.', 'info');
      }
    } catch (err) {
      setAutoDownloadOA(!nextVal);
      notify('Failed to update faculty settings: ' + (err.message || ''), 'error');
    } finally {
      setIsUpdatingSettings(false);
    }
  };

  if (!currentSyllabus && searchResults.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
          <Search className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">No Search Results Yet</h2>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Upload a syllabus and review the citations to execute prioritized searches on Google Books, Open Library, Internet Archive, and Crossref.
        </p>
        <button
          onClick={() => setActiveTab('upload')}
          className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs"
        >
          Go to Upload Page
        </button>
      </div>
    );
  }

  // Calculate access counts strictly by verified access_status
  const directPdfCount = searchResults.filter(r => r.access_status === 'PUBLIC_PDF_VERIFIED').length;
  const borrowRequiredCount = searchResults.filter(r => r.access_status === 'BORROW_REQUIRED').length;
  const previewCount = searchResults.filter(r => r.access_status === 'PREVIEW_ONLY').length;
  const metadataCount = searchResults.filter(r => 
    !r.access_status || 
    r.access_status === 'METADATA_ONLY' || 
    r.access_status === 'LINK_UNAVAILABLE' || 
    r.access_status === 'VERIFICATION_FAILED'
  ).length;

  return (
    <div className="max-w-7xl mx-auto space-y-6 py-6 animate-fade-in">
      {/* Section 13 Multi-Source Discovery & RAG Control Panel */}
      <BookDiscoveryRAGPanel />

      {/* Header & Actions */}

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
              Verified Public PDF & Repository Engine
            </span>
            <span className="text-xs text-slate-400">•</span>
            <span className="text-xs text-slate-500">{searchResults.length} Books Processed</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Book Access & Verification Results
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Strict title, author, and %PDF- verification across Internet Archive digital texts, open-access repositories, and university preprints.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => currentSyllabus && runLawfulSearch(currentSyllabus.id)}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-blue-600 ${loading ? 'animate-spin' : ''}`} />
            <span>Re-run Search</span>
          </button>

          <button
            onClick={() => setActiveTab('export')}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-md shadow-blue-600/20 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Report</span>
          </button>
        </div>
      </div>

      {/* Faculty Preference Banner: Automatically download and index verified open-access books */}
      <div className="bg-gradient-to-r from-blue-50/80 to-indigo-50/80 border border-blue-200/80 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
        <div className="flex items-start sm:items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
              <span>Faculty Automation Setting</span>
              <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-indigo-100 text-indigo-800">
                Lawful Open-Access Only
              </span>
            </h4>
            <p className="text-[11px] text-slate-600 mt-0.5">
              Automatically download and index verified open-access books into the RAG curriculum database when detected. Restricted and borrow-only items will never be auto-downloaded.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleToggleAutoDownload}
          disabled={isUpdatingSettings}
          className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-xs ${
            autoDownloadOA
              ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-600/20'
              : 'bg-white hover:bg-slate-100 text-slate-700 border border-slate-300'
          }`}
        >
          <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center ${autoDownloadOA ? 'bg-white text-emerald-700' : 'border border-slate-400'}`}>
            {autoDownloadOA && <Check className="w-2.5 h-2.5" />}
          </div>
          <span>{autoDownloadOA ? 'Auto-Download Active' : 'Enable Auto-Download'}</span>
        </button>
      </div>

      {/* Access Classification Pills Summary - strictly verified */}
      <div className="flex flex-wrap items-center gap-3 bg-white p-3.5 rounded-2xl border border-slate-200 shadow-xs text-xs">
        <span className="text-slate-500 font-medium text-[11px] uppercase tracking-wider">
          Access Status:
        </span>
        {directPdfCount > 0 ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-600" />
            <span>{directPdfCount} Direct PDF Verified</span>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-medium">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            <span>0 Direct PDF</span>
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span>{borrowRequiredCount} Borrow Required</span>
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-800 border border-blue-200 font-semibold">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          <span>{previewCount} Preview Available</span>
        </span>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200 font-medium">
          <span className="w-2 h-2 rounded-full bg-slate-400" />
          <span>{metadataCount} Metadata Only</span>
        </span>
      </div>

      {/* Filter and Search Toolbar */}
      <FilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        onReset={handleResetFilters}
      />

      {/* Grid of Book Cards */}
      {searchResults.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {searchResults.map((book) => (
            <BookCard 
              key={book.id || book.book_id} 
              book={book} 
              onStatusChange={() => {
                if (currentSyllabus) loadSearchResults(currentSyllabus.id, filters);
              }}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center text-slate-500 space-y-2">
          <p className="font-semibold text-sm text-slate-700">No books match your current filters.</p>
          <p className="text-xs">Try clearing the search query or adjusting the confidence slider.</p>
          <button
            onClick={handleResetFilters}
            className="mt-2 text-xs font-semibold text-blue-600 hover:text-blue-800"
          >
            Reset all filters
          </button>
        </div>
      )}

    </div>
  );
}
