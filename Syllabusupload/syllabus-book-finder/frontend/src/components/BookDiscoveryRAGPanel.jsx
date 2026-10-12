import React, { useState, useEffect } from 'react';
import { 
  BookOpen, 
  Search, 
  Download, 
  ShieldCheck, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  FileText, 
  Table, 
  Layers, 
  ExternalLink, 
  X, 
  Check, 
  Filter, 
  StopCircle, 
  RotateCcw, 
  Edit3, 
  Bookmark, 
  Award, 
  Database,
  Trash2
} from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function BookDiscoveryRAGPanel() {
  const { currentSyllabus, notify } = useApp();

  const [activeTab, setActiveTab] = useState('all'); // 'all', 'textbooks', 'reference_books'
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [batchDownloading, setBatchDownloading] = useState(false);

  // Modals & Panels
  const [selectedBookForSearch, setSelectedBookForSearch] = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [searchingBook, setSearchingBook] = useState(false);

  const [showMatrixModal, setShowMatrixModal] = useState(false);
  const [coverageMatrix, setCoverageMatrix] = useState([]);
  const [loadingMatrix, setLoadingMatrix] = useState(false);

  const [editingBook, setEditingBook] = useState(null);
  const [editForm, setEditForm] = useState({});

  // Active Background Jobs map: { [bookId]: jobObject }
  const [jobs, setJobs] = useState({});

  // Pre-validation state: { [url]: result }
  const [preValidations, setPreValidations] = useState({});
  const [validatingUrl, setValidatingUrl] = useState(null);

  useEffect(() => {
    if (currentSyllabus?.id) {
      loadDiscoveryBooks();
    }
  }, [currentSyllabus]);

  // Polling for active background jobs
  useEffect(() => {
    const activeJobIds = Object.keys(jobs).filter(
      id => jobs[id] && !['Completed', 'Borrowing required', 'Download unavailable', 'Failed', 'Cancelled'].includes(jobs[id].status)
    );

    if (activeJobIds.length === 0) return;

    const interval = setInterval(async () => {
      for (const bId of activeJobIds) {
        const currentJob = jobs[bId];
        if (!currentJob?.job_id) continue;
        try {
          const updated = await api.getDiscoveryJobStatus(currentJob.job_id);
          setJobs(prev => ({ ...prev, [bId]: updated }));
          if (updated.status === 'Completed') {
            notify(`RAG indexing completed for book: ${updated.message || ''}`, 'success');
            loadDiscoveryBooks();
          } else if (updated.status === 'Failed') {
            notify(`Download job failed: ${updated.error || updated.message}`, 'error');
          }
        } catch (err) {
          console.error('Error polling job:', err);
        }
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [jobs]);

  const loadDiscoveryBooks = async () => {
    if (!currentSyllabus?.id) return;
    setLoading(true);
    try {
      const res = await api.getDiscoveryBooks(currentSyllabus.id);
      setBooks(res.books || []);
    } catch (err) {
      console.error('Failed to load discovery books:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExtractFromSyllabus = async () => {
    if (!currentSyllabus?.id) {
      notify('Please select or upload a syllabus first.', 'warning');
      return;
    }
    setParsing(true);
    try {
      const res = await api.parseDiscoveryBooks(currentSyllabus.id);
      notify(`Successfully extracted ${res.textbooks_count} Textbooks and ${res.reference_books_count} Reference Books!`, 'success');
      loadDiscoveryBooks();
    } catch (err) {
      notify(`Extraction error: ${err.message}`, 'error');
    } finally {
      setParsing(false);
    }
  };

  const handleOpenSearchModal = async (book) => {
    setSelectedBookForSearch(book);
    setSearchingBook(true);
    setSearchResults(null);
    try {
      const res = await api.searchDiscoveryBook({
        book_id: book.id,
        title: book.book_title,
        authors: Array.isArray(book.authors) ? book.authors.join(', ') : book.authors,
        isbn: book.isbn_13 || book.isbn_10,
        resource_type: book.resource_type
      });
      setSearchResults(res);
    } catch (err) {
      notify(`Search error: ${err.message}`, 'error');
    } finally {
      setSearchingBook(false);
    }
  };

  const handlePreValidateLink = async (url) => {
    if (!url) return;
    setValidatingUrl(url);
    try {
      const res = await api.preValidateDiscoveryLink(url);
      setPreValidations(prev => ({ ...prev, [url]: res }));
      if (res.is_valid) {
        notify(`Verification Succeeded: ${res.status_label} (${res.mime_type})`, 'success');
      } else {
        notify(`Verification Notice: ${res.friendly_message}`, 'info');
      }
    } catch (err) {
      notify(`Pre-validation check failed: ${err.message}`, 'error');
    } finally {
      setValidatingUrl(null);
    }
  };

  const handleDownloadAndIndex = async (bookId) => {
    try {
      const res = await api.triggerDiscoveryDownloadAndIndex(bookId, currentSyllabus?.id);
      setJobs(prev => ({
        ...prev,
        [bookId]: {
          job_id: res.job_id,
          status: res.status,
          progress: res.progress,
          current_step: res.message
        }
      }));
      notify('Background download and RAG indexing pipeline started.', 'info');
    } catch (err) {
      notify(`Failed to launch download job: ${err.message}`, 'error');
    }
  };

  const handleCancelJob = async (bookId) => {
    const job = jobs[bookId];
    if (!job?.job_id) return;
    try {
      await api.cancelDiscoveryJob(job.job_id);
      setJobs(prev => ({
        ...prev,
        [bookId]: { ...prev[bookId], status: 'Cancelled', current_step: 'Cancelled by faculty' }
      }));
      notify('Job cancelled successfully.', 'info');
    } catch (err) {
      notify(`Failed to cancel job: ${err.message}`, 'error');
    }
  };

  const handleRetryJob = async (bookId) => {
    const job = jobs[bookId];
    if (!job?.job_id) return;
    try {
      const res = await api.retryDiscoveryJob(job.job_id);
      setJobs(prev => ({
        ...prev,
        [bookId]: {
          job_id: res.job_id,
          status: res.status,
          progress: 10,
          current_step: 'Retrying job...'
        }
      }));
      notify('Job retried.', 'info');
    } catch (err) {
      notify(`Failed to retry job: ${err.message}`, 'error');
    }
  };

  const handleBatchDownloadVerified = async () => {
    if (!currentSyllabus?.id) return;
    setBatchDownloading(true);
    try {
      const res = await api.batchDownloadVerifiedDiscovery(currentSyllabus.id);
      notify(res.message, 'success');
      if (res.jobs && res.jobs.length > 0) {
        const newJobs = { ...jobs };
        res.jobs.forEach(j => {
          newJobs[j.book_id] = {
            job_id: j.job_id,
            status: 'Searching',
            progress: 10,
            current_step: 'Batch job started'
          };
        });
        setJobs(newJobs);
      }
    } catch (err) {
      notify(`Batch download failed: ${err.message}`, 'error');
    } finally {
      setBatchDownloading(false);
    }
  };

  const handleReindexBook = async (bookId) => {
    try {
      notify('Re-indexing book content for RAG...', 'info');
      const res = await api.reindexDiscoveryBook(bookId);
      notify('Re-indexing complete!', 'success');
      loadDiscoveryBooks();
    } catch (err) {
      notify(`Re-index error: ${err.message}`, 'error');
    }
  };

  const handleRemoveFromIndex = async (bookId) => {
    if (!window.confirm('Are you sure you want to remove this book from the active RAG vector index?')) return;
    try {
      await api.removeDiscoveryBookIndex(bookId);
      notify('Book removed from RAG index.', 'success');
      loadDiscoveryBooks();
    } catch (err) {
      notify(`Error removing index: ${err.message}`, 'error');
    }
  };

  const handleOpenCoverageMatrix = async () => {
    if (!currentSyllabus?.id) return;
    setShowMatrixModal(true);
    setLoadingMatrix(true);
    try {
      const res = await api.getDiscoveryCoverageMatrix(currentSyllabus.id);
      setCoverageMatrix(res.alignment_matrix || []);
    } catch (err) {
      notify(`Failed to load coverage matrix: ${err.message}`, 'error');
    } finally {
      setLoadingMatrix(false);
    }
  };

  const handleSaveMetadata = async () => {
    if (!editingBook?.id) return;
    try {
      await api.updateDiscoveryBookMetadata(editingBook.id, editForm);
      notify('Metadata successfully updated.', 'success');
      setEditingBook(null);
      loadDiscoveryBooks();
    } catch (err) {
      notify(`Metadata update failed: ${err.message}`, 'error');
    }
  };

  // Filter books by active tab
  const filteredBooks = books.filter(b => {
    if (activeTab === 'textbooks') return b.resource_type === 'TEXTBOOK';
    if (activeTab === 'reference_books') return b.resource_type === 'REFERENCE_BOOK';
    return true;
  });

  const textbookCount = books.filter(b => b.resource_type === 'TEXTBOOK').length;
  const referenceCount = books.filter(b => b.resource_type === 'REFERENCE_BOOK').length;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mb-8">
      {/* Top Header Banner */}
      <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-blue-900 p-6 text-white">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-800/80 text-indigo-200 text-xs font-semibold uppercase tracking-wider mb-2 border border-indigo-700">
              <Layers className="w-3.5 h-3.5" /> Multi-Source Discovery & RAG Engine
            </div>
            <h2 className="text-2xl font-bold tracking-tight">Curriculum Book Discovery & Alignment</h2>
            <p className="text-indigo-200 text-sm mt-1 max-w-2xl">
              Extract prescribed textbooks and reference books separately, cross-verify candidate files across 13 repositories, and build local RAG vector embeddings for syllabus-aligned question generation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={handleExtractFromSyllabus}
              disabled={parsing || !currentSyllabus}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-500 hover:bg-indigo-400 text-white font-medium text-sm transition shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${parsing ? 'animate-spin' : ''}`} />
              {parsing ? 'Extracting Sections...' : 'Extract From Syllabus'}
            </button>

            <button
              onClick={handleBatchDownloadVerified}
              disabled={batchDownloading || books.length === 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition shadow-sm disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              {batchDownloading ? 'Downloading...' : 'Batch Download Verified'}
            </button>

            <button
              onClick={handleOpenCoverageMatrix}
              disabled={books.length === 0}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-white/10 hover:bg-white/20 text-white font-medium text-sm transition border border-white/20"
            >
              <Table className="w-4 h-4" />
              Coverage Matrix
            </button>
          </div>
        </div>

        {/* Section Tabs */}
        <div className="flex items-center gap-2 mt-6 pt-4 border-t border-indigo-700/60">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'all'
                ? 'bg-white text-indigo-950 font-semibold shadow-sm'
                : 'text-indigo-200 hover:text-white hover:bg-indigo-800/50'
            }`}
          >
            All Resources ({books.length})
          </button>

          <button
            onClick={() => setActiveTab('textbooks')}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'textbooks'
                ? 'bg-white text-indigo-950 font-semibold shadow-sm'
                : 'text-indigo-200 hover:text-white hover:bg-indigo-800/50'
            }`}
          >
            <Bookmark className="w-3.5 h-3.5 text-indigo-500" />
            Textbooks ({textbookCount})
          </button>

          <button
            onClick={() => setActiveTab('reference_books')}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'reference_books'
                ? 'bg-white text-indigo-950 font-semibold shadow-sm'
                : 'text-indigo-200 hover:text-white hover:bg-indigo-800/50'
            }`}
          >
            <Award className="w-3.5 h-3.5 text-amber-400" />
            Reference Books ({referenceCount})
          </button>
        </div>
      </div>

      {/* Book List / Cards */}
      <div className="p-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
            <p className="text-sm font-medium text-slate-600">Loading curriculum resources...</p>
          </div>
        ) : filteredBooks.length === 0 ? (
          <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <BookOpen className="w-12 h-12 text-slate-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-slate-700">No books found in this view</h3>
            <p className="text-slate-500 text-sm max-w-md mx-auto mt-1 mb-4">
              Click &quot;Extract From Syllabus&quot; above to parse prescribed textbooks and reference books separately from your syllabus sections.
            </p>
            <button
              onClick={handleExtractFromSyllabus}
              disabled={parsing || !currentSyllabus}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition"
            >
              <RefreshCw className={`w-4 h-4 ${parsing ? 'animate-spin' : ''}`} />
              Extract Prescribed & Reference Books
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredBooks.map((b) => {
              const currentJob = jobs[b.id];
              const isJobRunning = currentJob && !['Completed', 'Borrowing required', 'Download unavailable', 'Failed', 'Cancelled'].includes(currentJob.status);

              return (
                <div 
                  key={b.id} 
                  className={`border rounded-xl p-5 transition shadow-sm ${
                    b.resource_type === 'TEXTBOOK' 
                      ? 'border-indigo-100 bg-indigo-50/20 hover:border-indigo-300' 
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                    {/* Main Book Details */}
                    <div className="space-y-2 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Resource Type Badge */}
                        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                          b.resource_type === 'TEXTBOOK'
                            ? 'bg-indigo-100 text-indigo-800 border border-indigo-200'
                            : 'bg-amber-100 text-amber-800 border border-amber-200'
                        }`}>
                          {b.resource_type === 'TEXTBOOK' ? <Bookmark className="w-3 h-3" /> : <Award className="w-3 h-3" />}
                          {b.resource_type === 'TEXTBOOK' ? 'Prescribed Textbook' : 'Reference Book'}
                        </span>

                        {/* Metadata Confidence Badge */}
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <ShieldCheck className="w-3 h-3" />
                          {Math.round(b.metadata_confidence || 85)}% Confidence
                        </span>

                        {/* RAG Index Status Badge */}
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold ${
                          b.rag_status === 'Indexed'
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                            : b.rag_status === 'Downloaded (Unindexed)'
                            ? 'bg-blue-100 text-blue-800 border border-blue-300'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}>
                          <Database className="w-3 h-3" />
                          {b.rag_status === 'Indexed' ? `RAG: ${b.total_chunks} chunks indexed` : b.rag_status}
                        </span>

                        {b.is_reviewed && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            <Check className="w-3 h-3" /> Faculty Reviewed
                          </span>
                        )}
                      </div>

                      {/* Title & Subtitle */}
                      <div>
                        <h4 className="text-lg font-bold text-slate-900 leading-snug">
                          {b.book_title}
                          {b.subtitle && <span className="font-normal text-slate-500 text-sm ml-2">({b.subtitle})</span>}
                        </h4>
                      </div>

                      {/* Separated Bibliographic Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 pt-2 text-xs">
                        <div className="bg-white p-2 rounded-lg border border-slate-100 shadow-2xs">
                          <span className="text-slate-400 font-semibold block uppercase text-[10px]">Author(s)</span>
                          <span className="text-slate-700 font-medium truncate block" title={b.authors_display}>
                            {b.authors_display || 'Not available'}
                          </span>
                        </div>

                        <div className="bg-white p-2 rounded-lg border border-slate-100 shadow-2xs">
                          <span className="text-slate-400 font-semibold block uppercase text-[10px]">Publisher</span>
                          <span className="text-slate-700 font-medium truncate block" title={b.publisher}>
                            {b.publisher || 'Not available'}
                          </span>
                        </div>

                        <div className="bg-white p-2 rounded-lg border border-slate-100 shadow-2xs">
                          <span className="text-slate-400 font-semibold block uppercase text-[10px]">Edition</span>
                          <span className="text-slate-700 font-medium truncate block">
                            {b.edition || 'Not available'}
                          </span>
                        </div>

                        <div className="bg-white p-2 rounded-lg border border-slate-100 shadow-2xs">
                          <span className="text-slate-400 font-semibold block uppercase text-[10px]">Publication Year</span>
                          <span className="text-slate-700 font-medium truncate block">
                            {b.publication_year || 'Not available'}
                          </span>
                        </div>

                        <div className="bg-white p-2 rounded-lg border border-slate-100 shadow-2xs">
                          <span className="text-slate-400 font-semibold block uppercase text-[10px]">ISBN Identifier</span>
                          <span className="text-slate-700 font-medium truncate block font-mono text-[11px]" title={b.isbn_display}>
                            {b.isbn_display || b.isbn_13 || b.isbn_10 || 'Not available'}
                          </span>
                        </div>
                      </div>

                      {b.original_citation && (
                        <p className="text-[11px] text-slate-400 italic pt-1 truncate max-w-3xl">
                          Syllabus Citation: &quot;{b.original_citation}&quot;
                        </p>
                      )}

                      {/* Live Job Progress Bar if Active */}
                      {isJobRunning && (
                        <div className="mt-3 p-3 bg-indigo-50/80 rounded-lg border border-indigo-200 space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-indigo-900 flex items-center gap-2">
                              <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                              {currentJob.status}: {currentJob.current_step}
                            </span>
                            <span className="font-mono text-indigo-700 font-bold">{currentJob.progress || 10}%</span>
                          </div>
                          <div className="w-full bg-indigo-200 h-2 rounded-full overflow-hidden">
                            <div 
                              className="bg-indigo-600 h-full transition-all duration-300 rounded-full" 
                              style={{ width: `${currentJob.progress || 10}%` }}
                            />
                          </div>
                          <div className="flex justify-end pt-1">
                            <button
                              onClick={() => handleCancelJob(b.id)}
                              className="inline-flex items-center gap-1 text-[11px] text-rose-600 hover:text-rose-800 font-medium"
                            >
                              <StopCircle className="w-3 h-3" /> Cancel Job
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Finished with error or cancelled */}
                      {currentJob && ['Failed', 'Cancelled'].includes(currentJob.status) && (
                        <div className="mt-2 flex items-center justify-between p-2.5 bg-rose-50 rounded-lg border border-rose-200 text-xs text-rose-800">
                          <span className="flex items-center gap-1.5 font-medium">
                            <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                            {currentJob.status}: {currentJob.error || currentJob.current_step}
                          </span>
                          <button
                            onClick={() => handleRetryJob(b.id)}
                            className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:text-indigo-900 bg-white px-2 py-1 rounded border border-rose-200 shadow-2xs"
                          >
                            <RotateCcw className="w-3 h-3" /> Retry
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons Column */}
                    <div className="flex flex-row lg:flex-col items-center lg:items-end gap-2 shrink-0">
                      <button
                        onClick={() => handleOpenSearchModal(b)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold border border-indigo-200 transition"
                      >
                        <Search className="w-3.5 h-3.5" />
                        Search Repositories
                      </button>

                      {b.local_file_path ? (
                        <>
                          <a
                            href={`/api/discovery/file/${b.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-semibold border border-emerald-200 transition"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            Open Local Copy
                          </a>

                          <button
                            onClick={() => handleReindexBook(b.id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold border border-slate-200 transition"
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                            Re-index
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleDownloadAndIndex(b.id)}
                          disabled={isJobRunning}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition shadow-sm disabled:opacity-50"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download & Index
                        </button>
                      )}

                      <button
                        onClick={() => {
                          setEditingBook(b);
                          setEditForm({
                            book_title: b.book_title,
                            publisher: b.publisher,
                            edition: b.edition,
                            publication_year: b.publication_year,
                            isbn_10: b.isbn_10,
                            isbn_13: b.isbn_13,
                            resource_type: b.resource_type
                          });
                        }}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-slate-500 hover:text-slate-800 text-xs transition"
                      >
                        <Edit3 className="w-3 h-3" /> Edit Metadata
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Multi-Source Search & Candidate Pre-validation Drawer / Modal */}
      {selectedBookForSearch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="p-5 bg-gradient-to-r from-indigo-900 to-slate-900 text-white flex items-center justify-between">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
                  Candidate Discovery & Link Pre-validation
                </span>
                <h3 className="text-lg font-bold truncate max-w-xl">
                  {selectedBookForSearch.book_title}
                </h3>
              </div>
              <button 
                onClick={() => setSelectedBookForSearch(null)}
                className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 overflow-y-auto space-y-5 flex-1">
              {searchingBook ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                  <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
                  <p className="text-sm font-medium text-slate-600">
                    Querying 13 lawful repositories (Google Books, Internet Archive, Open Library, DOAB, Local Storage)...
                  </p>
                </div>
              ) : searchResults ? (
                <div className="space-y-4">
                  {/* Consolidated Summary Bar */}
                  <div className="bg-indigo-50/70 p-4 rounded-xl border border-indigo-100 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-xs text-indigo-950 font-bold">
                        Match Classification: <span className="text-indigo-700">{searchResults.match_classification}</span> ({searchResults.overall_match_score}%)
                      </div>
                      <div className="text-xs text-slate-600 mt-0.5">
                        Sources Providing Metadata: <span className="font-semibold text-slate-800">{searchResults.metadata_sources?.join(', ') || 'N/A'}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                        searchResults.is_verified_downloadable
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}>
                        {searchResults.is_verified_downloadable ? 'Verified Download Available' : 'Borrow / Metadata Only'}
                      </span>

                      <button
                        onClick={() => {
                          handleDownloadAndIndex(selectedBookForSearch.id);
                          setSelectedBookForSearch(null);
                        }}
                        className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs"
                      >
                        Download Best Match
                      </button>
                    </div>
                  </div>

                  {/* Candidates List */}
                  <div className="space-y-3">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Discovered Candidates ({searchResults.candidates?.length || 0})
                    </h5>

                    {searchResults.candidates?.map((cand, idx) => {
                      const dlUrl = cand.verified_download_url || cand.access_url;
                      const valResult = preValidations[dlUrl] || cand.pre_validation;

                      return (
                        <div 
                          key={idx}
                          className="border border-slate-200 rounded-xl p-4 bg-white hover:border-slate-300 transition shadow-2xs space-y-2.5"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded bg-slate-100 font-bold text-xs text-slate-800 border border-slate-200">
                                {cand.source}
                              </span>
                              <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                                cand.match_classification === 'Exact Match'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-blue-50 text-blue-700 border border-blue-200'
                              }`}>
                                {cand.match_classification || 'Candidate'} ({cand.match_score || cand.confidence_score}%)
                              </span>
                            </div>

                            {/* Access Type & Verification Badge */}
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-slate-500 font-medium">
                                {cand.rights_or_license || cand.access_type}
                              </span>
                            </div>
                          </div>

                          <div className="text-sm font-semibold text-slate-800">
                            {cand.title}
                          </div>

                          <div className="text-xs text-slate-500 flex flex-wrap gap-x-4 gap-y-1">
                            {cand.authors && <span>Author: <strong>{cand.authors}</strong></span>}
                            {cand.publisher && <span>Pub: <strong>{cand.publisher}</strong></span>}
                            {cand.edition && <span>Ed: <strong>{cand.edition}</strong></span>}
                            {cand.publication_year && <span>Year: <strong>{cand.publication_year}</strong></span>}
                            {cand.isbn && <span>ISBN: <strong className="font-mono">{cand.isbn}</strong></span>}
                          </div>

                          {/* Pre-validation Results Banner if verified */}
                          {valResult && (
                            <div className={`p-2.5 rounded-lg text-xs flex items-center justify-between ${
                              valResult.is_valid
                                ? 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                                : 'bg-rose-50 text-rose-900 border border-rose-200'
                            }`}>
                              <span className="flex items-center gap-1.5 font-medium">
                                {valResult.is_valid ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertCircle className="w-4 h-4 text-rose-600" />}
                                {valResult.status_label}: {valResult.friendly_message || valResult.user_friendly_message}
                              </span>
                              {valResult.mime_type && (
                                <span className="font-mono text-[11px] bg-white/70 px-1.5 py-0.5 rounded border border-emerald-200 font-semibold">
                                  {valResult.mime_type}
                                </span>
                              )}
                            </div>
                          )}

                          {/* Action Footer for Candidate */}
                          <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                            <span className="text-[11px] text-slate-400 italic">
                              {cand.match_summary || cand.remarks || ''}
                            </span>

                            <div className="flex items-center gap-2">
                              {dlUrl && (
                                <button
                                  onClick={() => handlePreValidateLink(dlUrl)}
                                  disabled={validatingUrl === dlUrl}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition"
                                >
                                  <ShieldCheck className={`w-3.5 h-3.5 ${validatingUrl === dlUrl ? 'animate-spin' : ''}`} />
                                  {validatingUrl === dlUrl ? 'Verifying...' : 'Pre-Validate Link'}
                                </button>
                              )}

                              {cand.access_url && (
                                <a
                                  href={cand.access_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium transition"
                                >
                                  <ExternalLink className="w-3.5 h-3.5" />
                                  View Item
                                </a>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Syllabus Alignment Matrix Modal */}
      {showMatrixModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
            <div className="p-5 bg-gradient-to-r from-indigo-900 to-blue-900 text-white flex items-center justify-between">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
                  Section 11 Curriculum Alignment
                </span>
                <h3 className="text-lg font-bold">Syllabus Topic to Textbook Alignment Matrix</h3>
              </div>
              <button 
                onClick={() => setShowMatrixModal(false)}
                className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              {loadingMatrix ? (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                  <RefreshCw className="w-8 h-8 animate-spin text-indigo-600 mb-3" />
                  <p className="text-sm font-medium text-slate-600">Building alignment matrix across curriculum units...</p>
                </div>
              ) : coverageMatrix.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <Table className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                  <p className="font-medium">No topics mapped yet. Ensure syllabus has extracted units.</p>
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-200 rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="py-3 px-3">Unit</th>
                        <th className="py-3 px-4">Syllabus Topic</th>
                        <th className="py-3 px-4">Prescribed / Reference Book</th>
                        <th className="py-3 px-3">Chapter</th>
                        <th className="py-3 px-3">Pages</th>
                        <th className="py-3 px-3">Relevance</th>
                        <th className="py-3 px-3">RAG Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-medium">
                      {coverageMatrix.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50/80 transition">
                          <td className="py-3 px-3 font-bold text-slate-900">Unit {row.unit_number || row.unit}</td>
                          <td className="py-3 px-4 text-slate-800">{row.syllabus_topic}</td>
                          <td className="py-3 px-4 text-slate-900 font-semibold">{row.textbook_title || row.textbook}</td>
                          <td className="py-3 px-3 text-slate-600">{row.chapter}</td>
                          <td className="py-3 px-3 text-slate-600 font-mono text-[11px]">{row.pages}</td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                              {Math.round((row.relevance_score || row.relevance || 0.8) * 100)}%
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                              (row.rag_status || '').toLowerCase().includes('index')
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}>
                              {row.rag_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Metadata Modal */}
      {editingBook && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 border border-slate-200 animate-in fade-in zoom-in-95 duration-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-bold text-slate-900">Edit Bibliographic Metadata</h3>
              <button onClick={() => setEditingBook(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700 block mb-1">Book Title</label>
                <input
                  type="text"
                  value={editForm.book_title || ''}
                  onChange={e => setEditForm({ ...editForm, book_title: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Resource Type</label>
                  <select
                    value={editForm.resource_type || 'TEXTBOOK'}
                    onChange={e => setEditForm({ ...editForm, resource_type: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg"
                  >
                    <option value="TEXTBOOK">Prescribed Textbook</option>
                    <option value="REFERENCE_BOOK">Reference Book</option>
                  </select>
                </div>

                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Publication Year</label>
                  <input
                    type="text"
                    value={editForm.publication_year || ''}
                    onChange={e => setEditForm({ ...editForm, publication_year: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Publisher</label>
                  <input
                    type="text"
                    value={editForm.publisher || ''}
                    onChange={e => setEditForm({ ...editForm, publisher: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>

                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Edition</label>
                  <input
                    type="text"
                    value={editForm.edition || ''}
                    onChange={e => setEditForm({ ...editForm, edition: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">ISBN-10</label>
                  <input
                    type="text"
                    value={editForm.isbn_10 || ''}
                    onChange={e => setEditForm({ ...editForm, isbn_10: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg font-mono text-xs"
                  />
                </div>

                <div>
                  <label className="font-semibold text-slate-700 block mb-1">ISBN-13</label>
                  <input
                    type="text"
                    value={editForm.isbn_13 || ''}
                    onChange={e => setEditForm({ ...editForm, isbn_13: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg font-mono text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                onClick={() => setEditingBook(null)}
                className="px-3 py-2 rounded-lg text-slate-600 hover:bg-slate-100 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveMetadata}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs"
              >
                Save Metadata
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
