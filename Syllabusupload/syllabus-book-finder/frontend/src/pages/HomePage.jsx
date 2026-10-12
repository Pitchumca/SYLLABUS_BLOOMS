import React from 'react';
import { 
  UploadCloud, 
  Search, 
  FileCheck, 
  BarChart2, 
  Download, 
  ShieldCheck, 
  Sparkles, 
  Cpu, 
  BookOpen, 
  CheckCircle2, 
  ArrowRight 
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import { api } from '../services/api';

export default function HomePage() {
  const { setActiveTab, setCurrentSyllabus, setBooks, notify, setLoading } = useApp();

  // Quick Demo Launcher: Load the included sample syllabus text and parse it immediately
  const handleLaunchSample = async () => {
    try {
      setLoading(true);
      notify('Loading sample Computer Science syllabus...', 'info');

      // Sample syllabus text built into client for instant one-click demo
      const sampleText = `VISVESVARAYA TECHNOLOGICAL UNIVERSITY, BELAGAVI
Course Title: Advanced Data Structures and Algorithms (21CS42)

TEXT BOOKS:
1. Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein, "Introduction to Algorithms", 3rd Edition, PHI Learning / MIT Press, 2009, ISBN: 978-0262033848.
2. Mark Allen Weiss, "Data Structures and Algorithm Analysis in C++", 4th Edition, Pearson Education, 2014, ISBN: 978-0132847377.
3. Ellis Horowitz, Sartaj Sahni, Sanguthevar Rajasekaran, "Fundamentals of Computer Algorithms", 2nd Edition, Universities Press, 2008, ISBN: 978-8173716126.

REFERENCE BOOKS:
1. Michael T. Goodrich, Roberto Tamassia, Michael H. Goldwasser, "Data Structures and Algorithms in Python", 1st Edition, John Wiley & Sons, 2013, ISBN: 978-1118290279.
2. Robert Sedgewick, Kevin Wayne, "Algorithms", 4th Edition, Addison-Wesley Professional, 2011, ISBN: 978-0321573513.
3. Anany Levitin, "Introduction to the Design and Analysis of Algorithms", 3rd Edition, Pearson, 2012, ISBN: 978-0132316811.
4. Alfred V. Aho, John E. Hopcroft, Jeffrey D. Ullman, "Data Structures and Algorithms", 1st Edition, Pearson Education, 1983, ISBN: 978-0201000238.`;

      // Upload text via dummy file or directly via parse
      // Create a blob file
      const blob = new Blob([sampleText], { type: 'application/pdf' });
      // We also have the pre-generated sample syllabus on backend, let's query backend list or upload
      const syllabuses = await api.getSyllabus(1).catch(() => null);

      if (syllabuses) {
        setCurrentSyllabus(syllabuses);
        const parsedBooks = await api.getBooks(syllabuses.id);
        if (parsedBooks.length > 0) {
          setBooks(parsedBooks);
        } else {
          const newBooks = await api.parseBooks(syllabuses.id);
          setBooks(newBooks);
        }
        notify('Sample syllabus loaded! Navigating to Review page.', 'success');
        setActiveTab('review');
      } else {
        // Direct to upload page
        setActiveTab('upload');
      }
    } catch (err) {
      setActiveTab('upload');
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    {
      num: '01',
      title: 'Upload Syllabus PDF',
      desc: 'Drag & drop your course curriculum PDF (up to 25MB). Fast text extraction with PyMuPDF, pdfplumber, and optional Tesseract OCR.',
      icon: UploadCloud,
    },
    {
      num: '02',
      title: 'Rule-Based NLP Extraction',
      desc: 'Accurately segments Text Books and Reference Books without expensive LLMs. Detects authors, editions, publishers, years, and ISBNs.',
      icon: Cpu,
    },
    {
      num: '03',
      title: 'Faculty Manual Review',
      desc: 'Review and edit citations in an interactive table. Toggle categories, add missing books, and merge duplicate records seamlessly.',
      icon: FileCheck,
    },
    {
      num: '04',
      title: 'Lawful Access Search & Export',
      desc: 'Search Google Books, Open Library, Crossref, and Internet Archive. Download styled Excel spreadsheets and ReportLab PDF audits.',
      icon: Download,
    },
  ];

  const features = [
    {
      title: 'Zero Paid LLM Dependencies',
      desc: 'High-speed deterministic parsing via rule-based NLP, regex heading boundaries, and line grouping tailored for Indian & global university formats.',
      icon: Cpu,
    },
    {
      title: '100% Lawful & Copyright-Safe',
      desc: 'Strictly queries legitimate public APIs and catalog repositories. Never accesses unauthorized file distribution or pirate websites.',
      icon: ShieldCheck,
    },
    {
      title: '8-Tier Access Classification',
      desc: 'Clear visual status badges: Verified Open Access, Public Domain, Controlled Lending, Preview Available, and Library Catalogue.',
      icon: Sparkles,
    },
    {
      title: 'Institutional Grade Exports',
      desc: 'Generate professional Excel audits with auto-filters, frozen panes, and custom ReportLab academic PDF summaries.',
      icon: BarChart2,
    },
  ];

  return (
    <div className="space-y-12 py-6 animate-fade-in">
      
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-blue-950 to-indigo-950 text-white p-8 sm:p-12 shadow-xl border border-slate-800">
        <div className="relative z-10 max-w-3xl space-y-6">
          
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-300 text-xs font-semibold tracking-wide">
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            <span>Academic Syllabus Intelligence</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight">
            AI-Powered Syllabus Textbook & Reference Book Finder
          </h1>

          <p className="text-base sm:text-lg text-slate-300 leading-relaxed max-w-2xl">
            Upload university syllabus PDFs, automatically extract bibliographic citations, verify lawful access paths across Open Library and Google Books, and export professional audit reports.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              onClick={() => setActiveTab('question-paper')}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-sm shadow-lg shadow-blue-600/30 hover:scale-102 transition-all flex items-center gap-2 cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              <span>Question Paper Generator</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={() => setActiveTab('upload')}
              className="px-5 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-200 hover:text-white font-semibold text-sm border border-slate-700 transition-colors flex items-center gap-2 cursor-pointer"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload Syllabus & Slides</span>
            </button>

            <button
              onClick={() => setActiveTab('about')}
              className="px-4 py-3 rounded-xl text-slate-300 hover:text-white font-medium text-sm transition-colors"
            >
              Usage & Policy
            </button>
          </div>

        </div>

        {/* Decorative background glow */}
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-1/4 -mb-16 w-80 h-80 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Workflow Steps */}
      <div>
        <div className="text-center max-w-2xl mx-auto mb-10">
          <span className="text-xs font-bold uppercase tracking-wider text-blue-600 block mb-1">
            Standard Operating Workflow
          </span>
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
            How It Works
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.num}
                className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-2xl font-black text-slate-200">
                      {step.num}
                    </span>
                    <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-700">
                      <Icon className="w-5 h-5" />
                    </div>
                  </div>
                  <h3 className="font-bold text-slate-900 text-base mb-2">
                    {step.title}
                  </h3>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    {step.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Core Advantages */}
      <div className="bg-slate-100/60 rounded-3xl p-8 sm:p-10 border border-slate-200">
        <div className="text-center max-w-xl mx-auto mb-8">
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
            Built Specifically for Faculty & Institutional Libraries
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((feat, idx) => {
            const Icon = feat.icon;
            return (
              <div key={idx} className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-2xs flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-blue-100/70 text-blue-700 flex items-center justify-center shrink-0 mt-0.5">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-slate-900 text-sm mb-1">{feat.title}</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">{feat.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
