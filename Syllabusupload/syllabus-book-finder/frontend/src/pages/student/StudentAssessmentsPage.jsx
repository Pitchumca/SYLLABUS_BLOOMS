import React from 'react';
import { Award, Clock, Play, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';
import { useApp } from '../../context/AppContext';

export default function StudentAssessmentsPage() {
  const { studentDashboardData, setSelectedStudentCourseId, setActiveTab, notify } = useApp();
  const pending = studentDashboardData?.pending_assessments || [];
  const completed = studentDashboardData?.recently_completed_assessments || [];

  return (
    <div className="space-y-6 pb-12 max-w-5xl mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Assessments & Diagnostic Testing
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Faculty-assigned diagnostic evaluations, adaptive quizzes, and competency reassessments.
          </p>
        </div>

        <span className="text-xs font-bold px-3 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200 self-start sm:self-auto">
          Phase 1 Active • Phase 2 Engine Ready
        </span>
      </div>

      {/* Pending Section */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <Clock className="w-4 h-4 text-amber-600" />
          Pending Assessments ({pending.length})
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {pending.map((p, idx) => (
            <div key={idx} className="p-5 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-4 hover:border-blue-300 transition-all flex flex-col justify-between">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-800">
                    {p.course_code} • {p.type.toUpperCase()}
                  </span>
                  <span className="text-xs text-rose-600 font-semibold">{p.due_date}</span>
                </div>

                <h3 className="text-sm font-bold text-slate-900">{p.title}</h3>
                <p className="text-xs text-slate-500">
                  Course: <strong className="text-slate-700">{p.course_name}</strong>
                </p>

                <div className="flex items-center gap-3 text-xs text-slate-600 pt-1">
                  <span>⏱ Duration: <strong>{p.duration_minutes} Mins</strong></span>
                  <span>•</span>
                  <span>📝 Questions: <strong>{p.total_questions}</strong></span>
                </div>
              </div>

              <button
                onClick={() => {
                  notify('Navigating to course curriculum assessment center...', 'info');
                  if (studentDashboardData?.enrolled_courses?.length > 0) {
                    setSelectedStudentCourseId(studentDashboardData.enrolled_courses[0].id);
                    setActiveTab('student-course-detail');
                  }
                }}
                className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-800 hover:to-indigo-700 text-white font-semibold text-xs shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Begin Assessment</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Completed Section */}
      <div className="space-y-4 pt-4">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          Recently Evaluated Assessments
        </h2>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold uppercase tracking-wider">
              <tr>
                <th className="px-5 py-3.5">Assessment Title</th>
                <th className="px-5 py-3.5">Course</th>
                <th className="px-5 py-3.5">Score</th>
                <th className="px-5 py-3.5">Percentage</th>
                <th className="px-5 py-3.5">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
              {completed.map((c, idx) => (
                <tr key={idx} className="hover:bg-slate-50/70">
                  <td className="px-5 py-3.5 font-bold text-slate-900">{c.title}</td>
                  <td className="px-5 py-3.5 font-semibold text-blue-700">{c.course_code}</td>
                  <td className="px-5 py-3.5 font-bold text-slate-900">{c.score} / {c.max_score}</td>
                  <td className="px-5 py-3.5">
                    <span className="px-2 py-0.5 rounded font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {c.percentage}%
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-slate-500">{c.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
