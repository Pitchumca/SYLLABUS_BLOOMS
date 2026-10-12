import React, { useState, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  FileSpreadsheet, 
  Image as ImageIcon, 
  AlertCircle, 
  CheckCircle2, 
  X, 
  Sparkles,
  BookOpen
} from 'lucide-react';
import { api } from '../services/api';

export default function TemplateUploadModal({
  isOpen,
  onClose,
  syllabusId,
  onExtractionSuccess
}) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleFileSelect = (file) => {
    setErrorMsg("");
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = ['docx', 'doc', 'pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'];
    if (!allowed.includes(ext)) {
      setErrorMsg(`Unsupported format '.${ext}'. Please upload DOCX, PDF, PNG/JPG, or XLSX.`);
      return;
    }
    setSelectedFile(file);
  };

  const handleUploadAndExtract = async () => {
    if (!selectedFile) return;
    try {
      setIsExtracting(true);
      setErrorMsg("");
      const res = await api.uploadAndExtractTemplate(selectedFile, syllabusId);
      onExtractionSuccess(res);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || "Failed to extract blueprint structure from template.");
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-5 animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <span className="p-2 bg-blue-50 text-blue-700 rounded-xl">
              <UploadCloud className="w-5 h-5" />
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Upload Question-Paper Template</h3>
              <p className="text-[11px] text-slate-500">Supports DOCX, PDF, Scanned PDF, PNG/JPG, and XLSX</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Drag and Drop Box */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (e.dataTransfer.files?.[0]) handleFileSelect(e.dataTransfer.files[0]);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
            dragOver 
              ? 'border-blue-500 bg-blue-50/60' 
              : selectedFile 
                ? 'border-emerald-400 bg-emerald-50/30' 
                : 'border-slate-200 hover:border-blue-400 hover:bg-blue-50/30'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx,.doc,.pdf,.png,.jpg,.jpeg,.xlsx,.xls"
            onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
            className="hidden"
          />

          {selectedFile ? (
            <div className="space-y-1">
              <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-1" />
              <span className="font-bold text-xs text-slate-800 block truncate max-w-xs mx-auto">
                {selectedFile.name}
              </span>
              <span className="text-[10px] text-slate-400">
                {(selectedFile.size / 1024).toFixed(1)} KB • Click or drop another file to change
              </span>
            </div>
          ) : (
            <div className="space-y-1.5">
              <UploadCloud className="w-8 h-8 text-slate-400 mx-auto mb-1" />
              <span className="text-xs font-bold text-slate-700 block">
                Click to browse or drag and drop question paper template
              </span>
              <span className="text-[11px] text-slate-400 block">
                Preserves headers, tables, OR choices, marks, and CO/Bloom allocations
              </span>
            </div>
          )}
        </div>

        {/* Supported Formats Pills */}
        <div className="flex items-center justify-center gap-2 flex-wrap text-[10px] text-slate-600 font-semibold">
          <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-md border border-blue-100 flex items-center gap-1">
            <FileText className="w-3 h-3" /> DOCX (Recommended)
          </span>
          <span className="px-2 py-0.5 bg-red-50 text-red-700 rounded-md border border-red-100 flex items-center gap-1">
            <FileText className="w-3 h-3" /> PDF / Scanned PDF
          </span>
          <span className="px-2 py-0.5 bg-amber-50 text-amber-700 rounded-md border border-amber-100 flex items-center gap-1">
            <ImageIcon className="w-3 h-3" /> Image (OCR)
          </span>
          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-md border border-emerald-100 flex items-center gap-1">
            <FileSpreadsheet className="w-3 h-3" /> XLSX Table
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
          >
            Cancel
          </button>
          
          <button
            type="button"
            onClick={handleUploadAndExtract}
            disabled={!selectedFile || isExtracting}
            className="flex items-center gap-2 px-4 py-2 text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-xs transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" />
            <span>{isExtracting ? "Extracting Structure & Tables..." : "Extract Blueprint"}</span>
          </button>
        </div>

      </div>
    </div>
  );
}
