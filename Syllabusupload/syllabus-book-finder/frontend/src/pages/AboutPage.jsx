import React from 'react';
import { 
  ShieldCheck, 
  BookOpen, 
  ExternalLink, 
  Lock, 
  CheckCircle2, 
  HelpCircle, 
  AlertCircle 
} from 'lucide-react';

export default function AboutPage() {
  const tiers = [
    {
      name: 'Verified open-access full text',
      color: 'bg-emerald-100 text-emerald-800 border-emerald-300',
      dot: 'bg-emerald-500',
      desc: 'Work is licensed under Creative Commons, DOAB, or published in an authorized unencumbered Open Access repository.',
    },
    {
      name: 'Public-domain full text',
      color: 'bg-emerald-100 text-emerald-800 border-emerald-300',
      dot: 'bg-emerald-500',
      desc: 'Copyright term has expired or work was dedicated to the public domain with full text lawful downloads.',
    },
    {
      name: 'Borrowing available',
      color: 'bg-blue-100 text-blue-800 border-blue-300',
      dot: 'bg-blue-500',
      desc: 'Controlled Digital Lending (CDL) via Open Library or Internet Archive lending collection (1-hour or 14-day loans).',
    },
    {
      name: 'Preview available',
      color: 'bg-sky-100 text-sky-800 border-sky-300',
      dot: 'bg-sky-500',
      desc: 'Substantial sample chapters, table of contents, and searchable index available lawfully via Google Books.',
    },
    {
      name: 'Catalogue record',
      color: 'bg-amber-100 text-amber-800 border-amber-300',
      dot: 'bg-amber-500',
      desc: 'WorldCat, Crossref, or Open Library metadata record to verify library holdings or locate campus physical copies.',
    },
    {
      name: 'Publisher or purchase page',
      color: 'bg-amber-100 text-amber-800 border-amber-300',
      dot: 'bg-amber-500',
      desc: 'Direct link to official publisher portal (Springer, Pearson, McGraw-Hill, IEEE) for institutional subscriptions.',
    },
    {
      name: 'General discovery link',
      color: 'bg-slate-100 text-slate-800 border-slate-300',
      dot: 'bg-slate-500',
      desc: 'Google Scholar and academic index discovery queries for supplementary citations.',
    },
    {
      name: 'No verified access found',
      color: 'bg-rose-100 text-rose-800 border-rose-300',
      dot: 'bg-rose-500',
      desc: 'No confident match or lawful open access link could be identified in the queried repositories.',
    },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-10 py-6 animate-fade-in">
      
      {/* Title */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
          About & Academic Usage Policy
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Guiding principles, copyright compliance, and lawful repository integrations.
        </p>
      </div>

      {/* Policy Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-8 shadow-xs space-y-6">
        
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              Lawful Access & Copyright Compliance Policy
            </h2>
            <p className="text-xs text-slate-600 leading-relaxed mt-2">
              The <b>AI-Powered Syllabus Textbook and Reference Book Finder</b> is designed specifically for academic faculty, department curriculum committees, and institutional librarians.
            </p>
          </div>
        </div>

        <div className="space-y-3 text-xs text-slate-600 bg-slate-50 p-5 rounded-2xl border border-slate-200/80">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span><b>No Pirated Sources:</b> The system does not query, index, or link to unauthorized copyright-infringing websites or pirate PDF hubs.</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span><b>No Automated Copyright Downloads:</b> The application never downloads copyrighted books onto servers. All links direct faculty to the legitimate publisher or library host.</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span><b>Rigorous Verification:</b> A publicly reachable PDF is never treated as open access unless its Creative Commons licence or public-domain status is formally confirmed by authoritative metadata.</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <span><b>Zero Cost LLMs:</b> Deterministic rule-based NLP and RapidFuzz matching are executed entirely locally without sending syllabus text to third-party paid AI APIs.</span>
          </div>
        </div>

      </div>

      {/* 8-Tier Access Classification Table */}
      <div className="bg-white rounded-3xl border border-slate-200 p-8 shadow-xs space-y-6">
        <h3 className="text-base font-bold text-slate-900">
          8-Tier Access Classification System
        </h3>
        <p className="text-xs text-slate-500">
          Every search result is evaluated and assigned one of eight color-coded access tiers:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tiers.map((t, idx) => (
            <div key={idx} className="p-4 rounded-xl border border-slate-200/80 bg-slate-50/50 space-y-2">
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${t.color}`}>
                <span className={`w-2 h-2 rounded-full ${t.dot}`} />
                <span>{t.name}</span>
              </span>
              <p className="text-[11px] text-slate-600 leading-relaxed">
                {t.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Supported APIs and Sources */}
      <div className="bg-white rounded-3xl border border-slate-200 p-8 shadow-xs space-y-4">
        <h3 className="text-base font-bold text-slate-900">
          Supported Academic Repositories & APIs
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-slate-600">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
            <span className="font-bold text-slate-900 block mb-0.5">Google Books API</span>
            Official volume metadata, viewability flags, preview links, and ISBN matching.
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
            <span className="font-bold text-slate-900 block mb-0.5">Open Library Search API</span>
            Non-profit library catalog, lending records, public scan indications, and author works.
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
            <span className="font-bold text-slate-900 block mb-0.5">Crossref REST API</span>
            Digital Object Identifiers (DOI), verified publisher citations, and Open Access licenses.
          </div>
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
            <span className="font-bold text-slate-900 block mb-0.5">Directory of Open Access Books (DOAB)</span>
            Peer-reviewed open access academic monographs under Creative Commons.
          </div>
        </div>
      </div>

    </div>
  );
}
