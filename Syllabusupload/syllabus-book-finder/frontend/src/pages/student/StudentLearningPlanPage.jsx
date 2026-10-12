import React from 'react';
import { Sparkles, BookOpen, FileText, CheckCircle2, Clock, AlertTriangle, ArrowRight } from 'lucide-react';
import { useApp } from '../../context/AppContext';

export default function StudentLearningPlanPage() {
  const { studentDashboardData, notify } = useApp();
  const weakTopics = studentDashboardData?.weak_topics || [];
  const activities = studentDashboardData?.recommended_learning_activities || [];

  return (
    <div className="space-y-6 pb-12 max-w-5xl mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Personalized Remedial Learning Plan
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Automated recommendations based on cognitive mastery thresholds across Course Outcomes and syllabus topics.
          </p>
        </div>

        <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 self-start sm:self-auto">
          Threshold: 60% (Proficient)
        </span>
      </div>

      {/* Weak Areas Banner */}
      <div className="p-4 bg-amber-50/70 border border-amber-200 rounded-2xl space-y-3">
        <h2 className="text-sm font-bold text-amber-900 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          Areas Requiring Cognitive Remediation
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {weakTopics.map((wt, idx) => (
            <div key={idx} className="p-3 bg-white rounded-xl border border-amber-200 shadow-xs flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-900 block">{wt.identifier}</span>
                <span className="text-[11px] text-slate-500">Mastery Level: {wt.score}% ({wt.category})</span>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                Remediation Active
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Remedial Activity Modules */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-600" />
          Recommended Learning Tasks
        </h2>

        <div className="space-y-3">
          {activities.map((act, idx) => (
            <div key={act.id || idx} className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 uppercase tracking-wide">
                  {act.type} • {act.duration}
                </span>
                <h3 className="text-sm font-bold text-slate-900">{act.title}</h3>
                <p className="text-xs text-slate-500">
                  Approved Repository Source: <strong className="text-slate-700">{act.source}</strong>
                </p>
              </div>

              <button
                onClick={() => notify(`Starting remedial study session: ${act.title}`, 'info')}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shrink-0 shadow-xs transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span>Study Resource</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
