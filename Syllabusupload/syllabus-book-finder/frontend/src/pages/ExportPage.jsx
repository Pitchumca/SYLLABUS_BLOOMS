import React, { useState, useEffect } from 'react';
import { 
  Download, 
  FileSpreadsheet, 
  FileText, 
  FileCode, 
  Clock, 
  CheckCircle2, 
  BookOpen, 
  ExternalLink 
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';

export default function ExportPage() {
  const { currentSyllabus, searchResults, setActiveTab, notify } = useApp();
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [history, setHistory] = useState([]);

  useEffect(() => {
    loadHistory();
  }, [currentSyllabus]);

  const loadHistory = async () => {
    try {
      const data = await api.getExportHistory(currentSyllabus?.id);
      setHistory(data);
    } catch (err) {
      console.error('Failed to load export history', err);
    }
  };

  if (!currentSyllabus && searchResults.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4 animate-fade-in">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
          <Download className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">No Syllabus to Export</h2>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Please upload and review a syllabus before generating institutional audit reports.
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

  const handleDownload = (format) => {
    if (!currentSyllabus) return;
    const url = api.getExportUrl(currentSyllabus.id, format, selectedCategory);
    window.open(url, '_blank');
    notify(`Generating ${format.toUpperCase()} report download...`, 'info');
    setTimeout(() => {
      loadHistory();
    }, 2000);
  };

  const exportFormats = [
    {
      id: 'excel',
      title: 'Formatted Excel Workbook',
      ext: '.xlsx',
      desc: 'Styled with OpenPyXL: Navy blue headers, frozen panes, auto-filters, KPI summary block, and auto-adjusted column widths.',
      icon: FileSpreadsheet,
      badge: 'Recommended for Faculty Audit',
      color: 'emerald',
    },
    {
      id: 'pdf',
      title: 'Academic PDF Report',
      ext: '.pdf',
      desc: 'Compiled with ReportLab: Academic typography, summary statistics table, status badges, and official running footers.',
      icon: FileText,
      badge: 'Print-Ready',
      color: 'rose',
    },
    {
      id: 'csv',
      title: 'RFC 4180 CSV Data',
      ext: '.csv',
      desc: 'Standard comma-separated format with UTF-8 BOM for maximum compatibility with Microsoft Excel, R, and Python Pandas.',
      icon: FileText,
      badge: 'Data Exchange',
      color: 'blue',
    },
    {
      id: 'json',
      title: 'Structured JSON Export',
      ext: '.json',
      desc: 'Complete machine-readable JSON object including syllabus metadata, extracted citations, and verified access links.',
      icon: FileCode,
      badge: 'API & Developers',
      color: 'purple',
    },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-8 py-6 animate-fade-in">
      
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Export & Report Generation
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Generate audit spreadsheets and PDF documentation for academic compliance and institutional library acquisition.
        </p>
      </div>

      {/* Filter Selector */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="font-semibold text-slate-900 text-xs block">Export Scope</span>
          <span className="text-xs text-slate-500">Choose which categories to include in the generated document</span>
        </div>
        <div className="flex items-center gap-2">
          {['All', 'Textbook', 'Reference Book'].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {cat === 'All' ? 'All Books' : cat + 's Only'}
            </button>
          ))}
        </div>
      </div>

      {/* Export Format Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {exportFormats.map((fmt) => {
          const Icon = fmt.icon;
          return (
            <div
              key={fmt.id}
              className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-800 flex items-center justify-center">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700">
                    {fmt.badge}
                  </span>
                </div>

                <h3 className="text-base font-bold text-slate-900 mb-1">
                  {fmt.title} <span className="text-xs text-slate-400 font-mono">{fmt.ext}</span>
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed mb-4">
                  {fmt.desc}
                </p>
              </div>

              <button
                onClick={() => handleDownload(fmt.id)}
                className="w-full py-2.5 rounded-xl bg-slate-900 hover:bg-blue-600 text-white text-xs font-semibold shadow-xs flex items-center justify-center gap-2 transition-colors"
              >
                <Download className="w-4 h-4" />
                <span>Download {fmt.title}</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* Export History */}
      {history.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-bold text-slate-900">Recent Export History</h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Format</th>
                  <th className="py-2.5 px-3">Filename</th>
                  <th className="py-2.5 px-3">Records</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.map((h) => (
                  <tr key={h.id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-3 font-semibold uppercase text-blue-700">{h.export_type}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-700">{h.filename}</td>
                    <td className="py-2.5 px-3 text-slate-600">{h.record_count}</td>
                    <td className="py-2.5 px-3 text-slate-400">{new Date(h.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
