import React from 'react';
import { ShieldCheck, BookOpen, ExternalLink } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function Footer() {
  const { setActiveTab } = useApp();

  return (
    <footer className="bg-white border-t border-slate-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
          
          {/* Col 1: Brand & Purpose */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-lg bg-blue-700 flex items-center justify-center text-white text-xs">
                <BookOpen className="w-3.5 h-3.5" />
              </div>
              <span className="font-bold text-slate-900 text-sm">
                AI-Powered Syllabus Book Finder
              </span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              Assisting faculty and higher education institutions in extracting textbook citations, auditing bibliographic metadata, and identifying verified lawful access paths.
            </p>
          </div>

          {/* Col 2: Lawful Access Notice */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80">
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800 mb-1">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>100% Lawful & Copyright Compliant</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Searches only official repositories (Google Books, Open Library, Crossref, Internet Archive, DOAB). No unauthorized downloads or pirate sources are ever utilized.
            </p>
          </div>

          {/* Col 3: Quick Links */}
          <div className="flex flex-col md:items-end text-xs text-slate-500 space-y-2">
            <span className="font-semibold text-slate-700 uppercase tracking-wider text-[10px]">
              Institutional Navigation
            </span>
            <div className="flex flex-wrap md:justify-end gap-x-4 gap-y-1">
              <button 
                onClick={() => setActiveTab('about')} 
                className="hover:text-blue-600 transition-colors"
              >
                Fair Use & Policy
              </button>
              <button 
                onClick={() => setActiveTab('upload')} 
                className="hover:text-blue-600 transition-colors"
              >
                Upload Syllabus
              </button>
              <button 
                onClick={() => setActiveTab('analytics')} 
                className="hover:text-blue-600 transition-colors"
              >
                Analytics Dashboard
              </button>
            </div>
            <div className="text-[11px] text-slate-400 pt-2">
              © {new Date().getFullYear()} AI Academic Library Tools • Built with FastAPI & React
            </div>
          </div>

        </div>
      </div>
    </footer>
  );
}
