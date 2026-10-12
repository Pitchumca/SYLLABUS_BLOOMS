import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Search, 
  CheckCheck, 
  AlertCircle, 
  RefreshCw, 
  Layers, 
  BookOpen, 
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  FileCheck,
  Download,
  Database,
  ExternalLink,
  X
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';
import BookTable from '../components/BookTable';
import AddBookModal from '../components/AddBookModal';
import MergeModal from '../components/MergeModal';

export default function ReviewPage() {
  const { 
    currentSyllabus, 
    books, 
    setBooks, 
    loadBooks, 
    runLawfulSearch, 
    loadSearchResults,
    setActiveTab, 
    notify, 
    loading 
  } = useApp();

  const [categoryFilter, setCategoryFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [mergeModalData, setMergeModalData] = useState({ isOpen: false, book: null });

  // Async Search & Indexing Pipeline States
  const [activeJob, setActiveJob] = useState(null);
  const [isStartingSearch, setIsStartingSearch] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [retryingBookId, setRetryingBookId] = useState(null);

  useEffect(() => {
    if (currentSyllabus) {
      loadBooks(currentSyllabus.id, categoryFilter, searchTerm);
    }
  }, [currentSyllabus, categoryFilter, searchTerm]);

  // Polling effect for active background job (every 2.5 seconds)
  useEffect(() => {
    if (!activeJob || ['COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'].includes(activeJob.status)) {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        const updated = await api.getBookSearchJob(activeJob.job_id);
        if (updated) {
          setActiveJob(updated);
          if (['COMPLETED', 'PARTIALLY_COMPLETED'].includes(updated.status)) {
            notify(updated.message || `Search job ${updated.status.toLowerCase().replace('_', ' ')}!`, 'success');
            if (currentSyllabus && loadSearchResults) {
              loadSearchResults(currentSyllabus.id);
            }
          } else if (updated.status === 'FAILED') {
            notify(updated.message || 'Book search job failed.', 'error');
          }
        }
      } catch (err) {
        console.warn('Job status poll notice:', err.message);
      }
    }, 2500);

    return () => clearInterval(pollInterval);
  }, [activeJob?.job_id, activeJob?.status, currentSyllabus, loadSearchResults]);

  const handleRefresh = () => {
    if (currentSyllabus) {
      loadBooks(currentSyllabus.id, categoryFilter, searchTerm);
    }
  };

  const handleConfirmAll = async () => {
    if (!currentSyllabus) return;
    try {
      await api.confirmAllBooks(currentSyllabus.id);
      notify('All records confirmed as reviewed!', 'success');
      handleRefresh();
    } catch (err) {
      notify('Failed to confirm all records', 'error');
    }
  };

  const handleStartSearchAndIndex = async () => {
    if (!currentSyllabus || isStartingSearch) return;
    setIsStartingSearch(true);
    setSearchError(null);

    try {
      const bookIds = books.map(b => b.id);
      const res = await api.startCourseBookSearchAndIndex(currentSyllabus.id, {
        book_ids: bookIds
      });

      notify(res.message || 'Search and indexing job queued!', 'info');

      // Fetch initial job state immediately
      const initialJob = await api.getBookSearchJob(res.job_id);
      setActiveJob(initialJob || {
        job_id: res.job_id,
        status: res.status || 'QUEUED',
        total_books: res.total_books || bookIds.length,
        completed_books: 0,
        failed_books: 0,
        progress_percentage: 0,
        current_stage: 'QUEUED',
        results: []
      });
    } catch (err) {
      console.error('Search initiation failure:', err);
      setSearchError({
        message: err.message || 'Failed to connect to search pipeline.',
        stage: err.stage || 'TRIGGER_FAILED',
        status: err.status,
        raw: err.rawBody || ''
      });
      notify(err.message || 'Search request failed', 'error');
    } finally {
      setIsStartingSearch(false);
    }
  };

  const handleRetryBook = async (bookId) => {
    if (!activeJob) return;
    setRetryingBookId(bookId);
    try {
      const res = await api.retryBookSearchInJob(activeJob.job_id, bookId);
      if (res.job) {
        setActiveJob(res.job);
      }
      notify(`Retrying search for book #${bookId}...`, 'info');
    } catch (err) {
      notify(`Retry error: ${err.message}`, 'error');
    } finally {
      setRetryingBookId(null);
    }
  };

  const totalTextbooks = books.filter(b => b.category === 'Textbook').length;
  const totalRefBooks = books.filter(b => b.category === 'Reference Book').length;
  const duplicateCount = books.filter(b => b.is_duplicate).length;

  const isSearchInProgress = isStartingSearch || (activeJob && ['QUEUED', 'RUNNING'].includes(activeJob.status));

  if (!currentSyllabus && books.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
          <BookOpen className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">No Syllabus Loaded</h2>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Please upload a syllabus PDF or use the sample syllabus to review extracted book records.
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

  return (
    <div className="max-w-7xl mx-auto space-y-6 py-6 animate-fade-in">
      
      {/* Header & KPI Summary */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Manual Review & Citation Verification
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Review parsed books, verify metadata, add missing records, and resolve duplicate citations before searching.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-xs transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-blue-600" />
            <span>Add Book</span>
          </button>

          <button
            onClick={handleConfirmAll}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 shadow-xs transition-colors"
          >
            <CheckCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Confirm All</span>
          </button>

          <button
            onClick={handleStartSearchAndIndex}
            disabled={isSearchInProgress || books.length === 0}
            className={`inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold text-white shadow-md transition-all ${
              isSearchInProgress 
                ? 'bg-blue-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700 shadow-blue-600/20 hover:scale-102'
            }`}
          >
            {isSearchInProgress ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Search className="w-3.5 h-3.5" />
            )}
            <span>
              {isStartingSearch
                ? 'Starting Search…'
                : isSearchInProgress
                ? `Searching (${activeJob?.progress_percentage || 0}%)`
                : 'Search Books & Find PDFs'}
            </span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Initiation Failure Banner with Diagnostic Stage */}
      {searchError && (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 text-xs space-y-2 animate-fade-in">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2 text-rose-800 font-semibold">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>Search Pipeline Error [{searchError.stage}]</span>
            </div>
            <button
              onClick={() => setSearchError(null)}
              className="text-rose-400 hover:text-rose-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <p className="text-rose-700 pl-6">{searchError.message}</p>
          <div className="pl-6 flex items-center gap-3 pt-1">
            <button
              onClick={handleStartSearchAndIndex}
              className="px-3 py-1 bg-rose-600 text-white rounded-lg font-medium hover:bg-rose-700"
            >
              Try Again
            </button>
            <span className="text-rose-500 text-[11px]">
              {searchError.stage === 'AUTHENTICATION_REQUIRED' && 'Please refresh token or log in again.'}
              {searchError.stage === 'ENDPOINT_NOT_FOUND' && 'Verify route is registered at POST /api/courses/{id}/books/search-and-index/.'}
              {searchError.stage === 'NETWORK_CONNECTIVITY_FAILURE' && 'FastAPI server at port 8000 is unreachable.'}
            </span>
          </div>
        </div>
      )}

      {/* Live Asynchronous Search & RAG Progress Tracker */}
      {activeJob && (
        <div className="bg-white rounded-2xl border border-blue-100 shadow-md p-5 space-y-4 animate-fade-in">
          {/* Tracker Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${
                activeJob.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-600' :
                activeJob.status === 'FAILED' ? 'bg-rose-50 text-rose-600' :
                'bg-blue-50 text-blue-600'
              }`}>
                {activeJob.status === 'COMPLETED' ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : activeJob.status === 'FAILED' ? (
                  <XCircle className="w-4 h-4" />
                ) : (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold text-slate-900">
                    Book Discovery & RAG Pipeline
                  </h2>
                  <span className="text-[10px] font-mono bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                    {activeJob.job_id}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                    activeJob.status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' :
                    activeJob.status === 'PARTIALLY_COMPLETED' ? 'bg-amber-100 text-amber-800' :
                    activeJob.status === 'FAILED' ? 'bg-rose-100 text-rose-800' :
                    'bg-blue-100 text-blue-800 animate-pulse'
                  }`}>
                    {activeJob.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {activeJob.message || 'Processing prescribed books independently across 8 open repositories...'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {['COMPLETED', 'PARTIALLY_COMPLETED'].includes(activeJob.status) && (
                <button
                  onClick={() => setActiveTab('results')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs"
                >
                  <span>View Results & PDFs</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
              <button
                onClick={() => setActiveJob(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
                title="Dismiss Progress Panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Progress Bar & Current Stage */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-slate-600">
              <span className="font-semibold text-slate-800">
                Stage: {activeJob.current_stage || 'INITIALIZING'}
                {activeJob.current_book ? ` — ${activeJob.current_book}` : ''}
              </span>
              <span className="font-bold text-blue-600">
                {activeJob.completed_books || 0} / {activeJob.total_books || 0} Books ({activeJob.progress_percentage || 0}%)
              </span>
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 rounded-full ${
                  activeJob.status === 'COMPLETED' ? 'bg-emerald-500' :
                  activeJob.status === 'FAILED' ? 'bg-rose-500' :
                  'bg-blue-600'
                }`}
                style={{ width: `${Math.max(5, activeJob.progress_percentage || 0)}%` }}
              />
            </div>
          </div>

          {/* Per-Book Live Status Table */}
          {activeJob.results && activeJob.results.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 uppercase font-semibold text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3">Prescribed Book</th>
                    <th className="py-2.5 px-3">Metadata Search</th>
                    <th className="py-2.5 px-3">File Verification</th>
                    <th className="py-2.5 px-3">Download</th>
                    <th className="py-2.5 px-3">RAG Status</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {activeJob.results.map((bookItem) => {
                    const hasError = bookItem.search_status === 'FAILED' || bookItem.download_status === 'FAILED' || bookItem.errors?.length > 0;
                    return (
                      <tr key={bookItem.book_id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-slate-900">{bookItem.book_title}</div>
                          <div className="text-[11px] text-slate-500">
                            {bookItem.authors || 'Unknown Author'} • {bookItem.category || 'Textbook'}
                          </div>
                          {bookItem.remarks && (
                            <div className="text-[10px] text-amber-700 italic mt-0.5">
                              {bookItem.remarks}
                            </div>
                          )}
                        </td>

                        {/* Search Status */}
                        <td className="py-2.5 px-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                            bookItem.search_status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700' :
                            bookItem.search_status === 'SEARCHING' ? 'bg-blue-50 text-blue-700 animate-pulse' :
                            bookItem.search_status === 'FAILED' ? 'bg-rose-50 text-rose-700' :
                            bookItem.search_status === 'RATE_LIMITED' ? 'bg-amber-50 text-amber-700' :
                            bookItem.search_status === 'TIMEOUT' ? 'bg-amber-50 text-amber-700' :
                            'bg-slate-100 text-slate-600'
                          }`}>
                            {bookItem.search_status === 'SEARCHING' && <RefreshCw className="w-2.5 h-2.5 animate-spin" />}
                            {bookItem.search_status}
                            {bookItem.candidates_found > 0 && ` (${bookItem.candidates_found})`}
                          </span>
                        </td>

                        {/* File Verification */}
                        <td className="py-2.5 px-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                            bookItem.verified_files > 0 ? 'bg-emerald-50 text-emerald-700' :
                            bookItem.search_status === 'COMPLETED' ? 'bg-slate-100 text-slate-600' :
                            'bg-slate-50 text-slate-400'
                          }`}>
                            {bookItem.verified_files > 0 ? (
                              <>
                                <FileCheck className="w-3 h-3 text-emerald-600" />
                                <span>Verified Full-Text</span>
                              </>
                            ) : (
                              <span>No Direct File</span>
                            )}
                          </span>
                        </td>

                        {/* Download Status */}
                        <td className="py-2.5 px-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                            bookItem.download_status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700' :
                            bookItem.download_status === 'DOWNLOADING' ? 'bg-blue-50 text-blue-700 animate-pulse' :
                            bookItem.download_status === 'FAILED' ? 'bg-rose-50 text-rose-700' :
                            'bg-slate-100 text-slate-500'
                          }`}>
                            {bookItem.download_status === 'DOWNLOADING' && <RefreshCw className="w-2.5 h-2.5 animate-spin" />}
                            {bookItem.download_status === 'COMPLETED' ? 'Saved to Course' : bookItem.download_status}
                          </span>
                        </td>

                        {/* RAG Status */}
                        <td className="py-2.5 px-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                            bookItem.rag_status === 'INDEXED' ? 'bg-purple-50 text-purple-700' :
                            bookItem.rag_status === 'INDEXING' ? 'bg-blue-50 text-blue-700 animate-pulse' :
                            bookItem.rag_status === 'METADATA_ONLY' ? 'bg-slate-100 text-slate-600' :
                            bookItem.rag_status === 'FAILED' ? 'bg-rose-50 text-rose-700' :
                            'bg-slate-50 text-slate-400'
                          }`}>
                            {bookItem.rag_status === 'INDEXED' && <Database className="w-3 h-3 text-purple-600" />}
                            {bookItem.rag_status}
                          </span>
                        </td>

                        {/* Actions */}
                        <td className="py-2.5 px-3 text-right">
                          {hasError ? (
                            <button
                              onClick={() => handleRetryBook(bookItem.book_id)}
                              disabled={retryingBookId === bookItem.book_id}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200 transition-colors"
                            >
                              <RefreshCw className={`w-3 h-3 ${retryingBookId === bookItem.book_id ? 'animate-spin' : ''}`} />
                              <span>{retryingBookId === bookItem.book_id ? 'Retrying…' : 'Retry'}</span>
                            </button>
                          ) : (
                            <span className="text-[10px] text-slate-400">Ready</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Collapsible Technical Diagnostics */}
          <div className="pt-1 border-t border-slate-100">
            <button
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900"
            >
              {showDiagnostics ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span>{showDiagnostics ? 'Hide Technical Diagnostics & Telemetry' : 'View Technical Diagnostics & Provider Telemetry'}</span>
            </button>

            {showDiagnostics && (
              <div className="mt-3 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs space-y-3 font-mono">
                <div>
                  <span className="font-bold text-slate-700">Repositories Queried:</span>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-1.5 text-[11px]">
                    {['google_books', 'open_library', 'internet_archive', 'oer_commons', 'crossref', 'semantic_scholar', 'doab', 'local_database'].map((src) => (
                      <div key={src} className="p-2 bg-white rounded border border-slate-200">
                        <div className="font-bold text-slate-800">{src.replace('_', ' ').toUpperCase()}</div>
                        <div className="text-[10px] text-slate-500">
                          Timeout: 20s (Connect: 5s, Read: 15s)
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {activeJob.results && (
                  <div className="space-y-1">
                    <span className="font-bold text-slate-700">Per-Book Diagnostics:</span>
                    {activeJob.results.map((b) => (
                      <div key={b.book_id} className="p-2 bg-white rounded border border-slate-200 text-[11px]">
                        <span className="font-bold">{b.book_title}</span>: 
                        <span className="text-slate-600 ml-1">
                          sources checked: {b.sources_checked}, candidates: {b.candidates_found}, access: {b.access_status}
                        </span>
                        {b.errors?.length > 0 && (
                          <div className="text-rose-600 text-[10px] mt-0.5">
                            Errors: {b.errors.join('; ')}
                          </div>
                        )}
                        {b.verified_download_url && (
                          <div className="text-blue-600 text-[10px] truncate mt-0.5">
                            URL: {b.verified_download_url}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Metric Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 block uppercase">Total Extracted</span>
          <span className="text-2xl font-bold text-slate-900 mt-1 block">{books.length}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 block uppercase">Textbooks</span>
          <span className="text-2xl font-bold text-blue-600 mt-1 block">{totalTextbooks}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 block uppercase">Reference Books</span>
          <span className="text-2xl font-bold text-purple-600 mt-1 block">{totalRefBooks}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-500 block uppercase">Duplicates Detected</span>
          <div className="flex items-center gap-1.5 mt-1">
            <span className={`text-2xl font-bold ${duplicateCount > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
              {duplicateCount}
            </span>
            {duplicateCount > 0 && (
              <span className="text-[10px] text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded font-medium">
                Merge needed
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-3 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button
            onClick={() => setCategoryFilter('All')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              categoryFilter === 'All'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All ({books.length})
          </button>
          <button
            onClick={() => setCategoryFilter('Textbook')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              categoryFilter === 'Textbook'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Textbooks ({totalTextbooks})
          </button>
          <button
            onClick={() => setCategoryFilter('Reference Book')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
              categoryFilter === 'Reference Book'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Reference Books ({totalRefBooks})
          </button>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search records in table..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
          />
        </div>
      </div>

      {/* Interactive Review Table - Preserved Intact */}
      <BookTable
        books={books}
        onRefresh={handleRefresh}
        onOpenMerge={(book) => setMergeModalData({ isOpen: true, book })}
      />

      {/* Modals */}
      {currentSyllabus && (
        <AddBookModal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          syllabusId={currentSyllabus.id}
          onBookAdded={handleRefresh}
        />
      )}

      <MergeModal
        isOpen={mergeModalData.isOpen}
        onClose={() => setMergeModalData({ isOpen: false, book: null })}
        book={mergeModalData.book}
        allBooks={books}
        onMerged={handleRefresh}
      />

    </div>
  );
}
