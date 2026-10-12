import React, { useEffect, useState } from 'react';
import { 
  GraduationCap, 
  BookOpen, 
  Award, 
  Sparkles, 
  TrendingUp, 
  Clock, 
  Bell, 
  ChevronRight, 
  AlertTriangle, 
  CheckCircle2, 
  ArrowUpRight, 
  Play, 
  FileText, 
  Layers, 
  Target,
  RefreshCw,
  Check
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid 
} from 'recharts';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';

export default function StudentDashboardPage() {
  const { 
    user, 
    setActiveTab, 
    setSelectedStudentCourseId, 
    studentDashboardData, 
    loadStudentDashboard,
    notify 
  } = useApp();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(studentDashboardData);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    setLoading(true);
    const res = await loadStudentDashboard();
    if (res) setData(res);
    setLoading(false);
  };

  const handleOpenCourse = (courseId) => {
    setSelectedStudentCourseId(courseId);
    setActiveTab('student-course-detail');
  };

  const handleStartDiagnostic = () => {
    if (data?.enrolled_courses?.length > 0) {
      setSelectedStudentCourseId(data.enrolled_courses[0].id);
      notify('Navigating to diagnostic curriculum assessment...', 'info');
      setActiveTab('student-course-detail');
    } else {
      notify('Please select an enrolled course to begin.', 'info');
    }
  };

  const handleMarkNotificationRead = async (notifId) => {
    try {
      await api.markNotificationRead(notifId);
      setData(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          notifications: prev.notifications.map(n => n.id === notifId ? { ...n, is_read: true } : n)
        };
      });
      notify('Notification marked as read', 'success');
    } catch (err) {
      console.error(err);
    }
  };

  const getMasteryColor = (cat) => {
    switch (cat) {
      case 'Mastered':
        return 'text-emerald-700 bg-emerald-50 border-emerald-200';
      case 'Advanced':
        return 'text-blue-700 bg-blue-50 border-blue-200';
      case 'Proficient':
        return 'text-indigo-700 bg-indigo-50 border-indigo-200';
      case 'Developing':
        return 'text-amber-700 bg-amber-50 border-amber-200';
      default:
        return 'text-rose-700 bg-rose-50 border-rose-200';
    }
  };

  if (loading && !data) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3">
        <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
        <p className="text-sm font-medium text-slate-600">Loading student learning dashboard...</p>
      </div>
    );
  }

  const profile = data?.student_profile;
  const courses = data?.enrolled_courses || [];
  const pending = data?.pending_assessments || [];
  const weakTopics = data?.weak_topics || [];
  const activities = data?.recommended_learning_activities || [];
  const deadlines = data?.upcoming_deadlines || [];
  const notifications = data?.notifications || [];
  const coSummary = data?.co_attainment_summary || [];
  const trend = data?.progress_trend || [];

  return (
    <div className="space-y-6 pb-12">
      
      {/* 1. Welcome Card */}
      <div className="relative overflow-hidden bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 rounded-2xl text-white p-6 sm:p-8 shadow-lg">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur border border-white/20 text-xs font-semibold tracking-wide text-blue-200">
              <GraduationCap className="w-3.5 h-3.5" />
              Student Academic Journey • {profile?.semester || 'IV Semester'} ({profile?.section || 'Section A'})
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Welcome back, {profile?.full_name || user?.full_name || 'Student'}!
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 max-w-2xl leading-relaxed">
              Register No: <span className="font-semibold text-white">{profile?.register_number || 'REG2023CS001'}</span> • Programme: <span className="font-semibold text-white">{profile?.programme || 'B.E. Computer Science & Engineering'}</span> • Standing: <span className="text-emerald-400 font-bold">{profile?.academic_standing || 'Good Standing'}</span>
            </p>
          </div>

          <div className="flex flex-wrap sm:flex-nowrap gap-3 shrink-0">
            <button
              onClick={() => {
                if (courses.length > 0) handleOpenCourse(courses[0].id);
              }}
              className="flex-1 sm:flex-initial px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs sm:text-sm shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>Continue Learning</span>
            </button>
            <button
              onClick={handleStartDiagnostic}
              className="flex-1 sm:flex-initial px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white border border-white/20 font-semibold text-xs sm:text-sm backdrop-blur transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <Target className="w-4 h-4 text-emerald-400" />
              <span>Start Diagnostic Assessment</span>
            </button>
          </div>
        </div>

        {/* Subtle background decoration */}
        <div className="absolute right-0 bottom-0 translate-x-12 translate-y-12 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* 2. Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-500 font-medium block">Current Mastery</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-2xl font-black text-slate-900">
                {data?.current_mastery_percentage || 68.5}%
              </span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${getMasteryColor(data?.current_mastery_category)}`}>
                {data?.current_mastery_category || 'Proficient'}
              </span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-700 flex items-center justify-center shrink-0">
            <BookOpen className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-500 font-medium block">Enrolled Courses</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-2xl font-black text-slate-900">{courses.length}</span>
              <span className="text-xs text-slate-500 font-semibold">Active this term</span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-500 font-medium block">Pending Assessments</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-2xl font-black text-amber-600">{pending.length}</span>
              <span className="text-xs text-amber-700 font-semibold">Action Required</span>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-500 font-medium block">Completed Tests</span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-2xl font-black text-slate-900">
                {data?.recently_completed_assessments?.length || 2}
              </span>
              <span className="text-xs text-emerald-600 font-semibold">Evaluated</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Main Grid: Courses & Learning Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column (8 cols): Enrolled Courses + Trend Chart + Course Outcomes */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Enrolled Courses */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">My Enrolled Courses</h2>
                <p className="text-xs text-slate-500">Access curriculum units, lecture notes, and syllabus materials</p>
              </div>
              <button 
                onClick={() => setActiveTab('student-courses')}
                className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
              >
                View Catalog <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {courses.map((c) => (
                <div 
                  key={c.id} 
                  className="p-4 rounded-xl border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all bg-slate-50/50 flex flex-col justify-between group"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-800">
                        {c.course_code}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getMasteryColor(c.mastery_category)}`}>
                        {c.mastery_category}
                      </span>
                    </div>

                    <h3 className="text-sm font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                      {c.course_name}
                    </h3>

                    <p className="text-xs text-slate-500">
                      Instructor: <span className="font-semibold text-slate-700">{c.faculty_name}</span>
                    </p>

                    <div className="space-y-1 pt-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Curriculum Progress</span>
                        <span className="font-bold text-slate-900">{c.progress_percentage}%</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div 
                          className="h-full rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 transition-all duration-500" 
                          style={{ width: `${c.progress_percentage}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleOpenCourse(c.id)}
                    className="mt-4 w-full py-2 px-3 rounded-lg bg-white border border-slate-200 hover:bg-blue-50 hover:border-blue-200 text-xs font-semibold text-blue-700 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <span>Enter Course Learning</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Progress Trend Chart */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">Mastery Progress Trend</h2>
                <p className="text-xs text-slate-500">Cognitive development across assessment cycles</p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" />
                <span>Overall Mastery Score</span>
              </div>
            </div>

            <div className="h-60 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="masteryGradient" x1="0" y1="0" x2="0" y2="1">
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
                  <Area type="monotone" dataKey="mastery" stroke="#2563eb" strokeWidth={2.5} fillOpacity={1} fill="url(#masteryGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Course Outcome Attainment Summary */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">Course Outcome (CO) Attainment</h2>
                <p className="text-xs text-slate-500">Cognitive competencies mapped from syllabus curriculum</p>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                Target: 60% Benchmark
              </span>
            </div>

            <div className="space-y-3">
              {coSummary.map((co, idx) => (
                <div key={idx} className="p-3 rounded-xl border border-slate-100 bg-slate-50/50 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-800">{co.co}</span>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">{co.attainment}%</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                        co.attainment >= 60 ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                      }`}>
                        {co.status}
                      </span>
                    </div>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-200 overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${co.attainment >= 60 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                      style={{ width: `${co.attainment}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Right Column (4 cols): Pending, Weak Topics, Activities, Notifications */}
        <div className="lg:col-span-4 space-y-6">

          {/* Pending Assessments */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Award className="w-4 h-4 text-blue-600" />
                Pending Assessments
              </h3>
              <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                {pending.length}
              </span>
            </div>

            <div className="space-y-3">
              {pending.map((p, idx) => (
                <div key={idx} className="p-3 rounded-xl border border-slate-200 bg-slate-50 hover:bg-blue-50/40 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-blue-100 text-blue-800">
                      {p.course_code} • {p.type.toUpperCase()}
                    </span>
                    <span className="text-[11px] font-semibold text-rose-600 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {p.due_date}
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 mt-2 line-clamp-2">
                    {p.title}
                  </h4>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2">
                    <span>{p.duration_minutes} Mins • {p.total_questions} Questions</span>
                    <button
                      onClick={handleStartDiagnostic}
                      className="text-xs font-bold text-blue-600 hover:text-blue-700 hover:underline"
                    >
                      Start Test →
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Weak Topics Identified */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                Weak Topics Identified
              </h3>
            </div>

            <div className="space-y-2.5">
              {weakTopics.map((wt, idx) => (
                <div key={idx} className="p-2.5 rounded-xl border border-amber-200/70 bg-amber-50/40">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-800 truncate max-w-[180px]">
                      {wt.identifier}
                    </span>
                    <span className="font-bold text-amber-700">{wt.score}%</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mt-1.5">
                    <span>{wt.category}</span>
                    <span className="text-blue-700 font-semibold">{wt.remediation_status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recommended Learning Activities */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                Recommended Activities
              </h3>
            </div>

            <div className="space-y-3">
              {activities.map((act) => (
                <div key={act.id} className="p-3 rounded-xl border border-slate-200 bg-slate-50/50 hover:border-indigo-200 transition-colors">
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-indigo-100 text-indigo-800 uppercase">
                    {act.type} • {act.duration}
                  </span>
                  <h4 className="text-xs font-bold text-slate-900 mt-1.5">
                    {act.title}
                  </h4>
                  <p className="text-[11px] text-slate-500 mt-0.5 truncate">
                    Source: {act.source}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Upcoming Deadlines */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-600" />
              Upcoming Deadlines
            </h3>

            <div className="space-y-2.5">
              {deadlines.map((d, idx) => (
                <div key={idx} className="flex items-start gap-2.5 p-2 rounded-lg bg-slate-50">
                  <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${d.urgency === 'high' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                  <div>
                    <h5 className="text-xs font-semibold text-slate-800">{d.title}</h5>
                    <span className="text-[11px] text-slate-500 block">{d.course} • {d.due}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Faculty Notifications */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Bell className="w-4 h-4 text-blue-600" />
                Faculty Notifications
              </h3>
            </div>

            <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
              {notifications.map((n) => (
                <div 
                  key={n.id} 
                  className={`p-2.5 rounded-xl border text-xs transition-colors ${
                    n.is_read ? 'border-slate-200 bg-slate-50/50' : 'border-blue-200 bg-blue-50/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900">{n.title}</span>
                    {!n.is_read && (
                      <button
                        onClick={() => handleMarkNotificationRead(n.id)}
                        className="text-[10px] text-blue-700 hover:underline flex items-center gap-0.5"
                        title="Mark as read"
                      >
                        <Check className="w-3 h-3" /> Mark read
                      </button>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                    {n.message}
                  </p>
                </div>
              ))}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
