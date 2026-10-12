import React from 'react';
import { 
  TrendingUp, 
  Award, 
  Target, 
  Layers, 
  CheckCircle2, 
  BarChart2, 
  Sparkles 
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid 
} from 'recharts';
import { useApp } from '../../context/AppContext';

export default function StudentProgressPage() {
  const { studentDashboardData } = useApp();

  const data = studentDashboardData;
  const trend = data?.progress_trend || [];
  const coSummary = data?.co_attainment_summary || [];
  const courses = data?.enrolled_courses || [];

  return (
    <div className="space-y-6 pb-12 max-w-6xl mx-auto">
      {/* Header */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            My Cognitive Progress & Mastery
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Real-time analytics across syllabus units, Course Outcomes (COs), and Bloom's Taxonomy cognitive dimensions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-center min-w-[120px]">
            <span className="text-[10px] text-blue-700 font-bold uppercase block">Overall Mastery</span>
            <span className="text-2xl font-black text-blue-900 block mt-0.5">{data?.current_mastery_percentage || 68.5}%</span>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Trend Area Chart */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Weekly Mastery Trend</h2>
              <p className="text-xs text-slate-500">Learning trajectory across assessment attempts</p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="progressGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="week" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                  formatter={(val) => [`${val}%`, 'Mastery Score']}
                />
                <Area type="monotone" dataKey="mastery" stroke="#2563eb" strokeWidth={2.5} fillOpacity={1} fill="url(#progressGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* CO Attainment Bar Chart */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Course Outcome Attainment (%)</h2>
              <p className="text-xs text-slate-500">Cognitive achievement vs 60% institutional target</p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={coSummary} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="co" stroke="#94a3b8" fontSize={10} tickLine={false} tickFormatter={(v) => v.split(':')[0]} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                  formatter={(val) => [`${val}%`, 'Attainment']}
                />
                <Bar dataKey="attainment" fill="#4f46e5" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

      {/* Course Mastery Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
        <h2 className="text-base font-bold text-slate-900">Course-Wise Cognitive Status</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {courses.map((c) => (
            <div key={c.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-800">
                  {c.course_code}
                </span>
                <span className="text-xs font-bold text-slate-900">{c.mastery_percentage}%</span>
              </div>

              <h3 className="text-sm font-bold text-slate-900">{c.course_name}</h3>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>Category</span>
                  <strong className="text-blue-700">{c.mastery_category}</strong>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-200 overflow-hidden">
                  <div 
                    className="h-full rounded-full bg-blue-600" 
                    style={{ width: `${c.mastery_percentage}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
