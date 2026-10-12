import React, { useEffect, useState } from 'react';
import { Library, BookOpen, FileText, Search, ExternalLink } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';

export default function StudentResourcesPage() {
  const { studentCourses, setSelectedStudentCourseId, setActiveTab } = useApp();
  const [selectedCourse, setSelectedCourse] = useState(studentCourses[0]?.id || null);
  const [courseDetails, setCourseDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedCourse) {
      setLoading(true);
      api.getStudentCourseDetails(selectedCourse)
        .then(data => setCourseDetails(data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [selectedCourse]);

  const materials = courseDetails?.materials || [];

  return (
    <div className="space-y-6 pb-12 max-w-6xl mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Library className="w-6 h-6 text-blue-600" />
            Verified Academic Resources & Prescribed Books
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Lawful open-access textbooks, reference citations, and faculty-uploaded lecture presentation notes.
          </p>
        </div>

        {/* Course Filter Dropdown */}
        {studentCourses.length > 0 && (
          <select
            value={selectedCourse || ''}
            onChange={(e) => setSelectedCourse(Number(e.target.value))}
            className="text-xs font-semibold px-3 py-2 rounded-xl border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {studentCourses.map(c => (
              <option key={c.id} value={c.id}>
                {c.course_code}: {c.course_name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {materials.map((m) => (
          <div key={m.id} className="p-4 bg-white rounded-xl border border-slate-200 shadow-xs space-y-2 hover:border-blue-300 transition-colors">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800 uppercase">
                {m.material_type.replace('_', ' ')}
              </span>
              <span className="text-[10px] font-semibold text-slate-400 uppercase">
                {m.format}
              </span>
            </div>

            <h3 className="text-sm font-bold text-slate-900">{m.title}</h3>
            <p className="text-xs text-slate-600 line-clamp-2">{m.meta_info}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
