import React, { useEffect, useState } from 'react';
import { 
  BookOpen, 
  Search, 
  ArrowUpRight, 
  GraduationCap, 
  Layers, 
  CheckCircle2, 
  Award,
  RefreshCw
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';

export default function StudentCoursesPage() {
  const { 
    setSelectedStudentCourseId, 
    setActiveTab, 
    studentCourses, 
    loadStudentCourses 
  } = useApp();

  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [courses, setCourses] = useState(studentCourses || []);

  useEffect(() => {
    fetchCourses();
  }, []);

  const fetchCourses = async () => {
    setLoading(true);
    const data = await loadStudentCourses();
    if (data) setCourses(data);
    setLoading(false);
  };

  const handleOpenCourse = (courseId) => {
    setSelectedStudentCourseId(courseId);
    setActiveTab('student-course-detail');
  };

  const filteredCourses = courses.filter(c => 
    c.course_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.course_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.faculty_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            My Enrolled Courses
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Browse active semester curricula, access verified learning materials, and track unit progress.
          </p>
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by code, title, faculty..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-slate-50/50"
          />
        </div>
      </div>

      {loading ? (
        <div className="min-h-[40vh] flex flex-col items-center justify-center gap-2">
          <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
          <span className="text-xs text-slate-500">Loading enrolled curricula...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredCourses.map((c) => (
            <div 
              key={c.id} 
              className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 hover:shadow-md hover:border-blue-300 transition-all flex flex-col justify-between group"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-blue-100 text-blue-800">
                    {c.course_code}
                  </span>
                  <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-100 text-slate-700">
                    {c.semester}
                  </span>
                </div>

                <h3 className="text-base font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                  {c.course_name}
                </h3>

                <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                  {c.description || "Course curriculum with syllabus modules, Course Outcomes mapping, and adaptive learning assessments."}
                </p>

                <div className="pt-2 border-t border-slate-100 space-y-2 text-xs text-slate-500">
                  <div className="flex items-center justify-between">
                    <span>Faculty Instructor:</span>
                    <strong className="text-slate-800">{c.faculty_name}</strong>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Syllabus Units:</span>
                    <strong className="text-slate-800">{c.unit_count} Units</strong>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Cognitive Mastery:</span>
                    <span className="px-2 py-0.5 rounded font-bold text-[10px] bg-blue-50 text-blue-700 border border-blue-200">
                      {c.mastery_category} ({c.mastery_percentage}%)
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="space-y-1 pt-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500 font-medium">Curriculum Covered</span>
                    <span className="font-bold text-slate-900">{c.progress_percentage}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div 
                      className="h-full rounded-full bg-gradient-to-r from-blue-600 to-indigo-600" 
                      style={{ width: `${c.progress_percentage}%` }}
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={() => handleOpenCourse(c.id)}
                className="mt-6 w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-800 hover:to-indigo-700 text-white font-semibold text-xs shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>Enter Course Learning</span>
                <ArrowUpRight className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
