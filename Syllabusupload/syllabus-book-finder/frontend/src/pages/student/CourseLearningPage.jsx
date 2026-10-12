import React, { useEffect, useState } from 'react';
import { 
  ArrowLeft, 
  BookOpen, 
  FileText, 
  Presentation, 
  Sparkles, 
  ChevronDown, 
  ChevronUp, 
  CheckCircle2, 
  Clock, 
  Award, 
  Layers, 
  GraduationCap, 
  Target, 
  Download,
  AlertCircle,
  Play,
  Library,
  Compass,
  ArrowUpRight
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';

export default function CourseLearningPage() {
  const { 
    selectedStudentCourseId, 
    setActiveTab, 
    notify,
    studentCourses 
  } = useApp();

  const [courseData, setCourseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTabSection, setActiveTabSection] = useState('units'); // 'units' | 'outcomes' | 'materials' | 'assessments'
  const [expandedUnits, setExpandedUnits] = useState({ 1: true });

  useEffect(() => {
    // If no course explicitly selected, pick first enrolled course
    const courseId = selectedStudentCourseId || (studentCourses.length > 0 ? studentCourses[0].id : null);
    if (courseId) {
      fetchCourseDetails(courseId);
    } else {
      setLoading(false);
    }
  }, [selectedStudentCourseId]);

  const fetchCourseDetails = async (id) => {
    try {
      setLoading(true);
      const res = await api.getStudentCourseDetails(id);
      setCourseData(res);
      // Auto-expand first unit
      if (res.units && res.units.length > 0) {
        setExpandedUnits({ [res.units[0].number]: true });
      }
    } catch (err) {
      notify(err.message || 'Failed to load course details', 'error');
    } finally {
      setLoading(false);
    }
  };

  const toggleUnit = (num) => {
    setExpandedUnits(prev => ({
      ...prev,
      [num]: !prev[num]
    }));
  };

  const getMasteryBadgeClass = (category) => {
    switch (category) {
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

  if (loading) {
    return (
      <div className="min-h-[65vh] flex flex-col items-center justify-center gap-3">
        <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-600">Retrieving syllabus curriculum & learning materials...</p>
      </div>
    );
  }

  if (!courseData) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 text-center p-6 bg-white rounded-2xl border border-slate-200">
        <BookOpen className="w-12 h-12 text-slate-400" />
        <div>
          <h2 className="text-lg font-bold text-slate-800">No Course Selected</h2>
          <p className="text-sm text-slate-500 max-w-sm mt-1">Please select an enrolled course from your dashboard or courses catalog to access learning modules.</p>
        </div>
        <button
          onClick={() => setActiveTab('student-dashboard')}
          className="px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  const rec = courseData.recommended_next_topic;
  const units = courseData.units || [];
  const materials = courseData.materials || [];
  const outcomes = courseData.course_outcomes || [];
  const bloomDist = courseData.bloom_distribution || {};

  return (
    <div className="space-y-6 pb-12">
      
      {/* Top Header Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setActiveTab('student-dashboard')}
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Dashboard
        </button>

        <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-3 py-1 rounded-full border border-blue-200">
          Curriculum Repository Synced
        </span>
      </div>

      {/* Course Hero Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8 space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-md text-xs font-bold bg-blue-700 text-white tracking-wide">
                {courseData.course_code}
              </span>
              <span className="px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                {courseData.semester}
              </span>
              <span className="px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700">
                {courseData.department}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              {courseData.course_name}
            </h1>

            <p className="text-xs sm:text-sm text-slate-600 max-w-3xl leading-relaxed">
              {courseData.description || "Comprehensive university curriculum syllabus mapped with continuous adaptive learning objectives and course outcomes."}
            </p>

            <div className="flex items-center gap-4 text-xs text-slate-500 pt-1">
              <span>Faculty: <strong className="text-slate-800">{courseData.faculty_name}</strong></span>
              <span>•</span>
              <span>Academic Year: <strong className="text-slate-800">{courseData.academic_year}</strong></span>
            </div>
          </div>

          {/* Key Metrics Pill Grid */}
          <div className="flex sm:grid sm:grid-cols-2 gap-3 shrink-0">
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-center min-w-[130px]">
              <span className="text-[11px] font-semibold text-slate-500 block">Unit Completion</span>
              <span className="text-2xl font-black text-slate-900 mt-0.5 block">
                {courseData.overall_unit_completion}%
              </span>
              <span className="text-[10px] text-slate-500 font-medium">Curriculum Covered</span>
            </div>

            <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-center min-w-[130px]">
              <span className="text-[11px] font-semibold text-blue-700 block">Course Mastery</span>
              <span className="text-2xl font-black text-blue-900 mt-0.5 block">
                {courseData.overall_course_mastery}%
              </span>
              <span className={`inline-block text-[10px] font-bold px-1.5 py-0.2 rounded border ${getMasteryBadgeClass(courseData.mastery_category)} mt-0.5`}>
                {courseData.mastery_category}
              </span>
            </div>
          </div>
        </div>

        {/* Recommended Next Topic Banner */}
        {rec && (
          <div className="p-4 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-blue-600 text-white shrink-0 mt-0.5">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-blue-800 uppercase tracking-wide">Recommended Next Topic</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded border ${getMasteryBadgeClass(rec.category)}`}>
                    Unit {rec.unit_number}: {rec.current_mastery}%
                  </span>
                </div>
                <h4 className="text-sm font-bold text-slate-900 mt-0.5">
                  {rec.topic_title}
                </h4>
                <p className="text-xs text-slate-600 mt-0.5">
                  {rec.reason}
                </p>
              </div>
            </div>

            <button
              onClick={() => {
                setActiveTabSection('units');
                setExpandedUnits(prev => ({ ...prev, [rec.unit_number]: true }));
                notify(`Viewing Unit ${rec.unit_number} learning materials.`, 'info');
              }}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 shrink-0 shadow-xs transition-colors cursor-pointer"
            >
              <span>Study Module</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex border-b border-slate-200 bg-white rounded-xl px-3 shadow-xs overflow-x-auto">
        <button
          onClick={() => setActiveTabSection('units')}
          className={`flex items-center gap-2 py-3.5 px-4 text-xs sm:text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${
            activeTabSection === 'units'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Syllabus Units & Topics ({units.length})</span>
        </button>

        <button
          onClick={() => setActiveTabSection('materials')}
          className={`flex items-center gap-2 py-3.5 px-4 text-xs sm:text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${
            activeTabSection === 'materials'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Library className="w-4 h-4" />
          <span>Prescribed Materials ({materials.length})</span>
        </button>

        <button
          onClick={() => setActiveTabSection('outcomes')}
          className={`flex items-center gap-2 py-3.5 px-4 text-xs sm:text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${
            activeTabSection === 'outcomes'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Target className="w-4 h-4" />
          <span>Course Outcomes & Bloom's ({outcomes.length})</span>
        </button>

        <button
          onClick={() => setActiveTabSection('assessments')}
          className={`flex items-center gap-2 py-3.5 px-4 text-xs sm:text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${
            activeTabSection === 'assessments'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Award className="w-4 h-4" />
          <span>Assessments ({courseData.pending_assessments_count + courseData.completed_assessments_count})</span>
        </button>
      </div>

      {/* SECTION 1: Syllabus Units & Topics Accordion */}
      {activeTabSection === 'units' && (
        <div className="space-y-4">
          <div className="p-4 bg-blue-50/70 border border-blue-200 rounded-xl text-xs text-blue-900 flex items-start gap-2.5">
            <BookOpen className="w-4 h-4 text-blue-700 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Syllabus extracted directly from approved institutional repository</p>
              <p className="text-blue-800/80 mt-0.5">
                Every unit and topic below is automatically aligned with course outcomes, difficulty ratings, and cognitive Bloom's taxonomy levels. Students cannot modify or re-upload curriculum text.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {units.map((unit) => {
              const isOpen = !!expandedUnits[unit.number];
              return (
                <div 
                  key={unit.number}
                  className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden transition-all"
                >
                  <div 
                    onClick={() => toggleUnit(unit.number)}
                    className="p-4 sm:p-5 flex items-center justify-between cursor-pointer hover:bg-slate-50/70 transition-colors select-none"
                  >
                    <div className="flex items-center gap-3.5 pr-2">
                      <div className="w-9 h-9 rounded-lg bg-blue-100 text-blue-800 font-extrabold text-sm flex items-center justify-center shrink-0">
                        {unit.number}
                      </div>
                      <div>
                        <h3 className="text-sm sm:text-base font-bold text-slate-900">
                          Unit {unit.number}: {unit.title}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-slate-500 font-medium">Completion: {unit.completion_percentage}%</span>
                          <span className="text-slate-300">•</span>
                          <span className={`text-[10px] font-bold px-2 py-0.2 rounded border ${getMasteryBadgeClass(unit.mastery_category)}`}>
                            {unit.mastery_category} ({unit.mastery_score}%)
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="hidden sm:block w-32 h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div 
                          className="h-full rounded-full bg-blue-600" 
                          style={{ width: `${unit.completion_percentage}%` }}
                        />
                      </div>
                      {isOpen ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="px-5 pb-5 pt-1 border-t border-slate-100 space-y-4">
                      <div className="space-y-1.5">
                        <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                          Prescribed Curriculum Topics
                        </h4>
                        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed bg-slate-50 p-3.5 rounded-lg border border-slate-200/70 whitespace-pre-line">
                          {unit.topics || "Standard modular curriculum components."}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-500">Unit Competency Benchmark:</span>
                          <span className="text-xs font-bold text-slate-800">Minimum 60% (Proficient)</span>
                        </div>

                        <button
                          onClick={() => {
                            setActiveTabSection('materials');
                            notify(`Browsing learning materials for Unit ${unit.number}`, 'info');
                          }}
                          className="text-xs font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer"
                        >
                          View Unit Reading Materials →
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 2: Prescribed Materials & Verified Lawful Resources */}
      {activeTabSection === 'materials' && (
        <div className="space-y-4">
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900 flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Lawful & Approved Academic Repository Materials</p>
              <p className="text-emerald-800/80 mt-0.5">
                All learning materials are curated strictly from faculty lecture slides, institutional notes, and lawful open repositories (Google Books, Open Library, Crossref, DOAB). No pirated book links are hosted.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {materials.map((mat) => {
              const isSlide = mat.material_type === 'lecture_slide';
              const isNote = mat.material_type === 'lecture_note';
              const isTextbook = mat.material_type === 'prescribed_textbook';

              return (
                <div 
                  key={mat.id}
                  className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs flex items-start gap-3.5 hover:border-blue-300 transition-colors"
                >
                  <div className={`p-2.5 rounded-xl shrink-0 ${
                    isSlide ? 'bg-amber-100 text-amber-800' : isNote ? 'bg-rose-100 text-rose-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {isSlide ? <Presentation className="w-5 h-5" /> : isNote ? <FileText className="w-5 h-5" /> : <BookOpen className="w-5 h-5" />}
                  </div>

                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded uppercase ${
                        isSlide ? 'bg-amber-50 text-amber-700 border border-amber-200' : isNote ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}>
                        {isTextbook ? 'Prescribed Textbook' : isSlide ? 'Lecture Slides' : isNote ? 'Lecture Notes' : 'Reference Book'}
                      </span>
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">
                        {mat.format}
                      </span>
                    </div>

                    <h4 className="text-xs sm:text-sm font-bold text-slate-900 truncate" title={mat.title}>
                      {mat.title}
                    </h4>

                    <p className="text-[11px] text-slate-500 line-clamp-2">
                      {mat.meta_info}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SECTION 3: Course Outcomes & Bloom's Taxonomy Distribution */}
      {activeTabSection === 'outcomes' && (
        <div className="space-y-6">
          
          {/* Bloom's Level Distribution Summary */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
            <h3 className="text-sm font-bold text-slate-900 mb-2">
              Bloom's Taxonomy Cognitive Level Distribution
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Balance of lower-order thinking skills (Remember, Understand) and higher-order engineering outcomes (Apply, Analyze, Evaluate, Create).
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
              {Object.entries(bloomDist).map(([level, count]) => (
                <div key={level} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-center">
                  <span className="text-[11px] font-bold text-slate-600 block truncate">{level}</span>
                  <span className="text-xl font-black text-blue-700 mt-0.5 block">{count}</span>
                  <span className="text-[10px] text-slate-400">Target Objectives</span>
                </div>
              ))}
            </div>
          </div>

          {/* Course Outcomes Mapping Cards */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-slate-900">
              Approved Course Outcomes (CO1 – CO5)
            </h3>

            {outcomes.map((co) => (
              <div key={co.code} className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-blue-700 to-indigo-600 text-white font-black text-sm flex items-center justify-center shrink-0">
                  {co.code}
                </div>
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">{co.code} Outcome</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {co.bloom_level}
                    </span>
                  </div>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    {co.description}
                  </p>
                </div>
              </div>
            ))}
          </div>

        </div>
      )}

      {/* SECTION 4: Assessments & Diagnostics */}
      {activeTabSection === 'assessments' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Course Assessment Center</h3>
              <p className="text-xs text-slate-500">Diagnostic, formative, and adaptive examinations for this course</p>
            </div>
          </div>

          <div className="p-5 rounded-xl border border-blue-200 bg-blue-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800 uppercase">
                Diagnostic Assessment Available
              </span>
              <h4 className="text-sm font-bold text-slate-900">
                Diagnostic Test: Data Structures Core & Asymptotic Bounds
              </h4>
              <p className="text-xs text-slate-600">
                10 Questions • 30 Minutes • Objective Questions Auto-Scored
              </p>
            </div>

            <button
              onClick={() => notify('Phase 2 will unlock full interactive diagnostic test execution.', 'info')}
              className="px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shrink-0 shadow-xs transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              <span>Begin Assessment</span>
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
