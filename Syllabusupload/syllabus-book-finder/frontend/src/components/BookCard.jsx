import React, { useState, useEffect } from 'react';
import { 
  ExternalLink, 
  Library, 
  CheckCircle2, 
  FileDown, 
  Database, 
  Sparkles, 
  Loader2, 
  RefreshCw, 
  BookOpen, 
  AlertCircle 
} from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function BookCard({ book, onAcquired, onStatusChange }) {
  const { currentSyllabus, notify } = useApp();
  const [currentBook, setCurrentBook] = useState(book);
  const [isAcquiring, setIsAcquiring] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [isIndexed, setIsIndexed] = useState(Boolean(book.local_file_path || book.is_stored));

  // Sync state if prop changes
  useEffect(() => {
    setCurrentBook(book);
    setIsIndexed(Boolean(book.local_file_path || book.is_stored));
  }, [book]);

  const isTextbook = currentBook.category === 'Textbook';
  const confidence = Math.round(currentBook.confidence_score || 0);

  // Determine Access Status strictly from verified state
  const accessStatus = currentBook.access_status || 
    (currentBook.access_tier === 'tier_1_direct_open' ? 'PUBLIC_PDF_VERIFIED' : 'METADATA_ONLY');

  const isPublicPdfVerified = accessStatus === 'PUBLIC_PDF_VERIFIED';
  const isPublicEpubVerified = accessStatus === 'PUBLIC_EPUB_VERIFIED';
  const isBorrowRequired = accessStatus === 'BORROW_REQUIRED';
  const isPreviewOnly = accessStatus === 'PREVIEW_ONLY';
  const isMetadataOnly = accessStatus === 'METADATA_ONLY';
  const isLinkUnavailable = accessStatus === 'LINK_UNAVAILABLE';
  const isVerificationFailed = accessStatus === 'VERIFICATION_FAILED';

  const isExactMatch = (confidence >= 80 && (
    (currentBook.remarks || '').toLowerCase().includes('exact') || 
    (currentBook.remarks || '').toLowerCase().includes('author')
  )) || confidence >= 85;

  // Access Tier Colors & Badges - strictly driven by accessStatus
  const getBadgeDetails = () => {
    if (isPublicPdfVerified) {
      return {
        bg: 'bg-emerald-50 text-emerald-800 border-emerald-300',
        dot: 'bg-emerald-500',
        label: 'Direct PDF Available',
        color: 'green'
      };
    } else if (isPublicEpubVerified) {
      return {
        bg: 'bg-emerald-50 text-emerald-800 border-emerald-300',
        dot: 'bg-emerald-500',
        label: 'Public EPUB Verified',
        color: 'green'
      };
    } else if (isBorrowRequired) {
      return {
        bg: 'bg-amber-50 text-amber-800 border-amber-300',
        dot: 'bg-amber-500',
        label: 'Borrow Required',
        color: 'amber'
      };
    } else if (isPreviewOnly) {
      return {
        bg: 'bg-blue-50 text-blue-800 border-blue-300',
        dot: 'bg-blue-500',
        label: 'Preview Only',
        color: 'blue'
      };
    } else if (isLinkUnavailable) {
      return {
        bg: 'bg-rose-50 text-rose-800 border-rose-300',
        dot: 'bg-rose-500',
        label: 'Link Unavailable',
        color: 'rose'
      };
    } else if (isVerificationFailed) {
      return {
        bg: 'bg-rose-50 text-rose-800 border-rose-300',
        dot: 'bg-rose-500',
        label: 'Verification Failed',
        color: 'rose'
      };
    } else {
      return {
        bg: 'bg-slate-100 text-slate-700 border-slate-300',
        dot: 'bg-slate-400',
        label: 'Metadata Only',
        color: 'slate'
      };
    }
  };

  const badge = getBadgeDetails();

  // Job progress polling helper
  const pollJob = (jobId) => {
    const interval = setInterval(async () => {
      try {
        const job = await api.getJobStatus(jobId);
        setActiveJob(job);
        const terminalStates = ['Completed', 'Borrowing required', 'Download unavailable', 'Failed'];
        if (terminalStates.includes(job.status)) {
          clearInterval(interval);
          setIsAcquiring(false);
          if (job.status === 'Completed') {
            setIsIndexed(true);
            setCurrentBook(prev => ({
              ...prev,
              local_file_path: job.local_file_path,
              checksum_sha256: job.checksum_sha256,
              is_stored: true
            }));
            notify(`Successfully downloaded and indexed "${currentBook.title}"!`, 'success');
            if (onAcquired) onAcquired(job);
          } else if (job.status === 'Borrowing required') {
            notify(`Borrowing required for "${currentBook.title}". Direct download is restricted.`, 'info');
          } else {
            notify(`Download job finished: ${job.status} (${job.error_message || ''})`, 'error');
          }
        }
      } catch (err) {
        clearInterval(interval);
        setIsAcquiring(false);
      }
    }, 1500);
  };

  // 1. Download & Index handler
  const handleAcquireAndIndex = async () => {
    try {
      setIsAcquiring(true);
      notify(`Initiating download & indexing for "${currentBook.title}"...`, 'info');

      // Use specific search result verify-and-download job endpoint if search_result id is available
      if (currentBook.id && currentBook.book_id) {
        const res = await api.verifyAndDownloadResult(currentBook.id);
        if (res.job_id) {
          pollJob(res.job_id);
          return;
        }
      }

      // Fallback to direct acquire
      const downloadTarget = currentBook.verified_download_url || currentBook.access_url;
      if (!downloadTarget) {
        notify('No verified download URL available for acquisition.', 'error');
        setIsAcquiring(false);
        return;
      }

      const rightsCheck = await api.verifyResourceRights(downloadTarget);
      if (!rightsCheck.is_eligible && !rightsCheck.can_download_and_index) {
        notify(`Acquisition blocked: ${rightsCheck.reasons?.join('; ') || 'Domain not permitted.'}`, 'error');
        setIsAcquiring(false);
        return;
      }

      const acquired = await api.acquireLawfulResource({
        source_url: downloadTarget,
        title: currentBook.title,
        authors: currentBook.authors,
        publisher: currentBook.publisher,
        edition: currentBook.edition,
        year: currentBook.publication_year,
        isbn: currentBook.isbn_13 || currentBook.isbn_10 || currentBook.isbn,
        source_repository: currentBook.source || 'Open Educational Source',
        syllabus_id: currentSyllabus?.id || null,
        book_id: currentBook.book_id || currentBook.id || null
      });

      setIsIndexed(true);
      notify(`Successfully indexed "${currentBook.title}"! Chunks aligned to syllabus.`, 'success');
      if (onAcquired) onAcquired(acquired);
    } catch (err) {
      notify(err.message || 'Failed to acquire and index resource', 'error');
    } finally {
      setIsAcquiring(false);
    }
  };

  // 2. Retry Verification handler
  const handleRetryVerification = async () => {
    if (!currentBook.id) return;
    try {
      setIsRetrying(true);
      notify(`Retrying verification for "${currentBook.title}"...`, 'info');
      const updated = await api.retryVerification(currentBook.id);
      setCurrentBook(prev => ({ ...prev, ...updated }));
      if (onStatusChange) onStatusChange(updated);
      notify(`Verification updated: ${updated.access_status} (${updated.verification_message || ''})`, 'success');
    } catch (err) {
      notify(err.message || 'Retry verification failed', 'error');
    } finally {
      setIsRetrying(false);
    }
  };

  // URLs for navigation buttons
  const borrowUrl = currentBook.internet_archive_item_url || 
    (currentBook.internet_archive_identifier 
      ? `https://archive.org/details/${currentBook.internet_archive_identifier}` 
      : currentBook.access_url);

  const previewUrl = currentBook.access_url;
  const catalogueUrl = currentBook.access_url || currentBook.internet_archive_item_url;
  const directPdfUrl = currentBook.verified_download_url || currentBook.access_url;

  // Title formatting with subtitle
  const displayTitle = currentBook.subtitle && 
    !currentBook.title?.toLowerCase().includes(currentBook.subtitle.toLowerCase())
    ? `${currentBook.title}: ${currentBook.subtitle}`
    : currentBook.title;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/90 p-5 shadow-xs hover:shadow-md transition-all flex flex-col justify-between group">
      
      {/* Top Header: Category & Access Badge */}
      <div>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold tracking-wide uppercase ${
                isTextbook
                  ? 'bg-indigo-50 text-indigo-700 border border-indigo-200/60'
                  : 'bg-purple-50 text-purple-700 border border-purple-200/60'
              }`}
            >
              {currentBook.category || 'Reference'}
            </span>

            {isExactMatch && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3 h-3" />
                Exact Title & Author
              </span>
            )}

            {isIndexed && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                <Database className="w-3 h-3" />
                Indexed in DB
              </span>
            )}
          </div>

          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${badge.bg}`}>
            <span className={`w-2 h-2 rounded-full ${badge.dot}`} />
            <span className="truncate max-w-[170px]">{badge.label}</span>
          </span>
        </div>

        {/* Book Title */}
        <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-700 transition-colors line-clamp-2 leading-snug mb-1">
          {displayTitle}
        </h3>

        {/* Authors */}
        <p className="text-xs text-slate-600 font-medium mb-3 line-clamp-1">
          {currentBook.authors ? `By ${currentBook.authors}` : 'Author not specified'}
        </p>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 gap-y-1.5 gap-x-2 text-[11px] text-slate-600 bg-slate-50/70 p-3 rounded-xl border border-slate-100 mb-3">
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Edition</span>
            <span className="font-medium text-slate-800 truncate block">{currentBook.edition || '—'}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Publisher</span>
            <span className="font-medium text-slate-800 truncate block">{currentBook.publisher || '—'}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">Year</span>
            <span className="font-medium text-slate-800 block">{currentBook.publication_year || '—'}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px] uppercase font-semibold">ISBN</span>
            <span className="font-medium text-slate-800 font-mono block truncate">
              {currentBook.isbn_13 || currentBook.isbn_10 || currentBook.isbn || '—'}
            </span>
          </div>
        </div>

        {/* Match Confidence Progress Bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-slate-500 font-medium text-[11px]">Match Confidence</span>
            <span className={`font-bold ${
              confidence >= 80 ? 'text-emerald-600' : confidence >= 50 ? 'text-blue-600' : 'text-amber-600'
            }`}>
              {confidence}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full transition-all rounded-full ${
                confidence >= 80 ? 'bg-emerald-500' : confidence >= 50 ? 'bg-blue-500' : 'bg-amber-500'
              }`}
              style={{ width: `${confidence}%` }}
            />
          </div>
        </div>

        {/* Verification Status & Remarks */}
        {(currentBook.verification_message || currentBook.remarks) && (
          <p className="text-[11px] text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-200/60 mb-3 line-clamp-2">
            <span className="font-semibold text-slate-700">Verification: </span>
            {currentBook.verification_http_status && (
              <span className={`mr-1 px-1 py-0.2 rounded text-[10px] font-mono font-bold ${
                currentBook.verification_http_status === 200 || currentBook.verification_http_status === 206
                  ? 'bg-emerald-100 text-emerald-800'
                  : currentBook.verification_http_status === 401
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-rose-100 text-rose-800'
              }`}>
                HTTP {currentBook.verification_http_status}
              </span>
            )}
            {currentBook.verification_message || currentBook.remarks}
          </p>
        )}

        {/* Live Job Progress Banner */}
        {activeJob && ['Searching', 'Metadata matched', 'Checking licence/access', 'Verifying file', 'Downloading', 'Extracting text', 'Indexing for RAG'].includes(activeJob.status) && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-2.5 mb-3 text-xs">
            <div className="flex items-center justify-between text-indigo-900 font-semibold mb-1">
              <span className="flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                <span>{activeJob.status}</span>
              </span>
              <span className="text-[11px] font-mono">{activeJob.progress_pct}%</span>
            </div>
            <div className="w-full bg-indigo-200/60 rounded-full h-1.5 overflow-hidden">
              <div 
                className="bg-indigo-600 h-full rounded-full transition-all duration-300"
                style={{ width: `${activeJob.progress_pct}%` }}
              />
            </div>
            {activeJob.current_step && (
              <span className="text-[10px] text-indigo-700 mt-1 block truncate">
                {activeJob.current_step}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Footer: Source & Access Actions */}
      <div className="pt-3 border-t border-slate-100 flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 truncate">
            <Library className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span className="truncate font-medium text-slate-600">{currentBook.source || 'Direct Search'}</span>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Condition 1: Public PDF Verified */}
            {isPublicPdfVerified && (
              isIndexed ? (
                <>
                  <a
                    href={directPdfUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs hover:shadow transition-all shrink-0"
                    title="Open verified PDF file"
                  >
                    <FileDown className="w-3.5 h-3.5" />
                    <span>Open PDF</span>
                  </a>
                  <button
                    type="button"
                    onClick={handleAcquireAndIndex}
                    disabled={isAcquiring}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-all shrink-0"
                    title="Re-run text extraction and RAG indexing"
                  >
                    {isAcquiring ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    <span>Re-index</span>
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={handleAcquireAndIndex}
                  disabled={isAcquiring}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs hover:shadow transition-all shrink-0"
                  title="Lawfully download, extract text, and index into curriculum database"
                >
                  {isAcquiring ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Indexing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Download & Index</span>
                    </>
                  )}
                </button>
              )
            )}

            {/* Condition 2: Borrow Required */}
            {isBorrowRequired && (
              <a
                href={borrowUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white shadow-xs hover:shadow transition-all shrink-0"
                title="Lending required on Internet Archive. Open lawful item details page."
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Borrow / View on Internet Archive</span>
              </a>
            )}

            {/* Condition 3: Preview Only */}
            {isPreviewOnly && (
              <a
                href={previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs hover:shadow transition-all shrink-0"
                title="Open preview page"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Open Preview</span>
              </a>
            )}

            {/* Condition 4: Metadata Only */}
            {isMetadataOnly && (
              <a
                href={catalogueUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 shadow-xs transition-all shrink-0"
                title="View catalogue record"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>View Catalogue Record</span>
              </a>
            )}

            {/* Condition 5: Verification Failed or Link Unavailable */}
            {(isVerificationFailed || isLinkUnavailable) && (
              <button
                type="button"
                onClick={handleRetryVerification}
                disabled={isRetrying}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 shadow-xs transition-all shrink-0"
                title="Re-verify download access against official repository endpoint"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
                <span>Retry Verification</span>
              </button>
            )}

            {/* Fallback if none of the above and access_url exists */}
            {!isPublicPdfVerified && !isBorrowRequired && !isPreviewOnly && !isMetadataOnly && !isVerificationFailed && !isLinkUnavailable && (
              currentBook.access_url ? (
                <a
                  href={currentBook.access_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-xs hover:shadow transition-all shrink-0"
                >
                  <span>Link</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span className="text-xs text-slate-400 italic">No link</span>
              )
            )}
          </div>
        </div>
      </div>

    </div>
  );
}
