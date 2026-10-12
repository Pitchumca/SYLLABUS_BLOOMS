import React, { useEffect } from 'react';
import { 
  BarChart, 
  Bar, 
  PieChart, 
  Pie, 
  Cell, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer 
} from 'recharts';
import { 
  BarChart3, 
  BookOpen, 
  ShieldCheck, 
  CheckCircle2, 
  TrendingUp, 
  Layers 
} from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function AnalyticsPage() {
  const { currentSyllabus, analytics, loadAnalytics, setActiveTab } = useApp();

  useEffect(() => {
    if (currentSyllabus) {
      loadAnalytics(currentSyllabus.id);
    }
  }, [currentSyllabus]);

  if (!currentSyllabus || !analytics || analytics.total_books === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16 space-y-4 animate-fade-in">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
          <BarChart3 className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">No Analytics Data Available</h2>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Upload and review a syllabus to populate metric cards and interactive visual charts.
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

  // Category Pie Colors
  const CATEGORY_COLORS = ['#3B82F6', '#8B5CF6'];

  return (
    <div className="max-w-7xl mx-auto space-y-8 py-6 animate-fade-in">
      
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
          Syllabus Bibliographic Analytics
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Visual analysis of textbook distribution, lawful access classifications, and repository discovery.
        </p>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        
        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Total Books</span>
          <span className="text-2xl font-bold text-slate-900 mt-1 block">{analytics.total_books}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Textbooks</span>
          <span className="text-2xl font-bold text-blue-600 mt-1 block">{analytics.total_textbooks}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Reference Books</span>
          <span className="text-2xl font-bold text-purple-600 mt-1 block">{analytics.total_reference_books}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Open Access</span>
          <span className="text-2xl font-bold text-emerald-600 mt-1 block">{analytics.verified_open_access_count}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Preview / Borrow</span>
          <span className="text-2xl font-bold text-sky-600 mt-1 block">{analytics.preview_or_borrowing_count}</span>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Avg Confidence</span>
          <span className="text-2xl font-bold text-indigo-600 mt-1 block">{analytics.average_confidence_score}%</span>
        </div>

      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Chart 1: Books by Category */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Books by Category</h3>
          <p className="text-xs text-slate-500 mb-4">Proportion of required textbooks vs. supplementary reference readings</p>
          
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics.books_by_category}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={5}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {analytics.books_by_category.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Results by Access Classification */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Results by Access Type</h3>
          <p className="text-xs text-slate-500 mb-4">Distribution across the 8 lawful accessibility tiers</p>
          
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.results_by_access_type} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" name="Books" radius={[6, 6, 0, 0]}>
                  {analytics.results_by_access_type.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color || '#3B82F6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 3: Results by Source Repository */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Results by Academic Source</h3>
          <p className="text-xs text-slate-500 mb-4">Breakdown of matched records across authorized discovery APIs</p>
          
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.results_by_source} layout="vertical" margin={{ top: 10, right: 20, left: 40, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E2E8F0" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" name="Matched Records" fill="#0284C7" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 4: Confidence Score Distribution */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Match Confidence Distribution</h3>
          <p className="text-xs text-slate-500 mb-4">Bibliographic similarity scores (RapidFuzz title, author & ISBN)</p>
          
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.confidence_distribution} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" name="Books in Range" fill="#6366F1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

    </div>
  );
}
