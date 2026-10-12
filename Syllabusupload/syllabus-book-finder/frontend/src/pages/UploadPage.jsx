import React, { useState, useEffect, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  Trash2, 
  Save, 
  ArrowRight, 
  Scan, 
  Sparkles,
  CheckCircle2, 
  AlertCircle,
  RefreshCw,
  Server
} from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function UploadPage() {
  const { 
    currentSyllabus, 
    setCurrentSyllabus, 
    setBooks, 
    setActiveTab, 
    notify, 
    loading, 
    setLoading 
  } = useApp();

  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [extractedText, setExtractedText] = useState(currentSyllabus?.extracted_text || '');
  const [isOcrLoading, setIsOcrLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking'); // 'online' | 'offline' | 'checking'
  const fileInputRef = useRef(null);

  // Check backend server connection on mount and poll periodically
  useEffect(() => {
    checkServerConnection();
    const interval = setInterval(() => {
      checkServerConnection(true);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const checkServerConnection = async (silent = false) => {
    try {
      if (!silent) setBackendStatus('checking');
      await api.checkHealth();
      setBackendStatus('online');
    } catch {
      setBackendStatus('offline');
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file) => {
    // 1. Check extension
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      notify('Invalid file format. Please upload a PDF document (.pdf).', 'error');
      return;
    }
    // 2. Check 25MB limit
    const maxBytes = 25 * 1024 * 1024;
    if (file.size > maxBytes) {
      notify('File size exceeds the 25MB limit. Please upload a smaller syllabus.', 'error');
      return;
    }

    setSelectedFile(file);
    processUpload(file);
  };

  const processUpload = async (file) => {
    try {
      setLoading(true);
      setUploadProgress(25);
      
      const interval = setInterval(() => {
        setUploadProgress((prev) => (prev < 90 ? prev + 15 : prev));
      }, 180);

      const result = await api.uploadSyllabus(file);
      clearInterval(interval);
      setUploadProgress(100);

      setCurrentSyllabus(result);
      setExtractedText(result.extracted_text || '');
      setBackendStatus('online');
      notify(`PDF uploaded successfully! Extracted ${result.page_count} pages.`, 'success');
    } catch (err) {
      notify(err.message || 'Failed to upload syllabus PDF', 'error');
      setSelectedFile(null);
      checkServerConnection();
    } finally {
      setLoading(false);
    }
  };

  // One-click loader for the pre-packaged sample syllabus
  const handleLoadSample = async () => {
    try {
      setLoading(true);
      notify('Loading pre-packaged sample syllabus...', 'info');
      const result = await api.loadSampleSyllabus();
      setCurrentSyllabus(result);
      setExtractedText(result.extracted_text || '');
      setBackendStatus('online');
      notify('Sample syllabus loaded successfully! Click "Segment & Extract Books" to proceed.', 'success');
    } catch (err) {
      notify(err.message || 'Failed to load sample syllabus', 'error');
      checkServerConnection();
    } finally {
      setLoading(false);
    }
  };

  const handleRunOcr = async () => {
    if (!currentSyllabus) return;
    try {
      setIsOcrLoading(true);
      notify('Running Tesseract OCR on syllabus pages...', 'info');
      const updated = await api.triggerOCR(currentSyllabus.id);
      setCurrentSyllabus(updated);
      setExtractedText(updated.extracted_text || '');
      notify('OCR text extraction completed!', 'success');
    } catch (err) {
      notify(err.message || 'OCR processing failed. You can paste syllabus text directly.', 'error');
    } finally {
      setIsOcrLoading(false);
    }
  };

  const handleSaveText = async () => {
    if (!currentSyllabus) return;
    try {
      await api.updateSyllabusText(currentSyllabus.id, extractedText);
      notify('Syllabus text updated successfully', 'success');
    } catch (err) {
      notify('Failed to update text', 'error');
    }
  };

  const handleExtractBooks = async () => {
    if (!currentSyllabus) {
      notify('Please upload a syllabus PDF first.', 'error');
      return;
    }
    if (!extractedText.trim()) {
      notify('Extracted syllabus text is empty. Please upload a valid PDF or paste text.', 'error');
      return;
    }

    try {
      setLoading(true);
      notify('Segmenting Textbook & Reference Book sections with rule-based NLP...', 'info');
      const parsedBooks = await api.parseBooks(currentSyllabus.id, extractedText);
      setBooks(parsedBooks);
      notify(`Successfully extracted ${parsedBooks.length} books!`, 'success');
      setActiveTab('review');
    } catch (err) {
      notify(err.message || 'Failed to extract books from syllabus', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setCurrentSyllabus(null);
    setExtractedText('');
    setUploadProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 py-6 animate-fade-in">
      
      {/* Page Title and Server Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
            Upload Syllabus Document
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Upload course syllabus in PDF format (up to 25 MB) to extract textbook citations.
          </p>
        </div>

        {/* Backend Connection Status Badge */}
        <div className="flex items-center gap-2">
          {backendStatus === 'online' && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Backend Connected (Port 8000)</span>
            </span>
          )}
          {backendStatus === 'offline' && (
            <button
              onClick={checkServerConnection}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-300 hover:bg-amber-100 transition-colors"
              title="Click to re-check connection"
            >
              <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
              <span>Backend Offline — Click to Retry</span>
            </button>
          )}
        </div>
      </div>

      {/* Backend offline alert banner if needed */}
      {backendStatus === 'offline' && (
        <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 text-xs text-amber-900 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold">Backend Server Not Responding</span>
            <p className="text-amber-800">
              The FastAPI backend server is not reachable on port 8000. Please make sure to start it in a separate terminal:
            </p>
            <code className="block font-mono bg-amber-100/80 p-2 rounded-lg text-amber-950 font-semibold mt-1">
              cd backend &amp;&amp; .\.venv\Scripts\activate &amp;&amp; uvicorn app.main:app --reload --port 8000
            </code>
          </div>
        </div>
      )}

      {/* Drag & Drop Upload Zone */}
      {!currentSyllabus ? (
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-3xl p-10 text-center transition-all ${
            dragActive
              ? 'border-blue-500 bg-blue-50/70 scale-101'
              : 'border-slate-300 hover:border-slate-400 bg-white'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="hidden"
            id="pdf-upload-input"
          />

          <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4 shadow-xs">
            <UploadCloud className="w-8 h-8" />
          </div>

          <h3 className="text-base font-bold text-slate-900 mb-1">
            Drag and drop your Syllabus PDF here
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mb-6">
            Supports Indian university syllabi (VTU, Anna Univ, Mumbai Univ, AICTE) and standard academic PDFs up to 25MB.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <label
              htmlFor="pdf-upload-input"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs cursor-pointer transition-all hover:scale-102"
            >
              <FileText className="w-4 h-4" />
              <span>Select PDF File</span>
            </label>

            <button
              onClick={handleLoadSample}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>Load Sample Syllabus (Data Structures)</span>
            </button>
          </div>
        </div>
      ) : (
        /* File Details Card */
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900 truncate max-w-md">
                {currentSyllabus.original_filename}
              </h4>
              <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                <span>{(currentSyllabus.file_size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
                <span>•</span>
                <span>{currentSyllabus.page_count} Pages</span>
                <span>•</span>
                <span className="text-blue-600 font-medium">{currentSyllabus.extraction_method}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-center">
            <button
              onClick={handleRunOcr}
              disabled={isOcrLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              title="Run Tesseract OCR if text is scanned or missing"
            >
              <Scan className={`w-3.5 h-3.5 text-slate-600 ${isOcrLoading ? 'animate-spin' : ''}`} />
              <span>{isOcrLoading ? 'Running OCR...' : 'Run OCR Fallback'}</span>
            </button>
            <button
              onClick={handleRemoveFile}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Replace File</span>
            </button>
          </div>
        </div>
      )}

      {/* Upload Progress Bar */}
      {loading && uploadProgress > 0 && uploadProgress < 100 && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-medium text-slate-600">
            <span>Uploading & Extracting text...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-600 h-full rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Editable Extracted Syllabus Text Area */}
      {currentSyllabus && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Extracted Syllabus Text</h3>
              <p className="text-xs text-slate-500">
                You can review or manually edit citations before parsing.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSaveText}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save Edits</span>
              </button>
            </div>
          </div>

          <textarea
            value={extractedText}
            onChange={(e) => setExtractedText(e.target.value)}
            rows={14}
            className="w-full p-4 text-xs font-mono bg-slate-50 border border-slate-200 rounded-xl text-slate-800 leading-relaxed focus:ring-2 focus:ring-blue-500 focus:outline-hidden resize-y"
            placeholder="Extracted syllabus text will appear here. You can also paste text directly."
          />

          {/* Action to proceed to Book Parsing or Question Paper */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <span className="text-xs text-slate-400">
              {extractedText.length} characters • {extractedText.split('\n').length} lines
            </span>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setActiveTab('question-paper')}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-xs font-bold shadow-md transition-all cursor-pointer"
              >
                <Sparkles className="w-4 h-4" />
                <span>Question Paper & Blueprint</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={handleExtractBooks}
                disabled={loading}
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-md shadow-blue-600/20 hover:scale-102 transition-all cursor-pointer"
              >
                <span>Segment & Extract Books</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
