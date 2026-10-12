import React, { useState } from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ShieldCheck, 
  Plus, 
  Trash2, 
  Save, 
  Sparkles, 
  Sliders, 
  Info, 
  ChevronDown, 
  ChevronUp,
  FileCheck,
  HelpCircle,
  Download,
  FileText
} from 'lucide-react';
import { api } from '../services/api';

const ALL_BLOOM_LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6"];
const ALL_CO_LEVELS = ["CO1", "CO2", "CO3", "CO4", "CO5", "CO6"];

export default function ExtractedBlueprintReviewer({
  initialBlueprint,
  confidenceScores,
  initialValidation,
  extractionStatus = "extracted",
  fileFormat = "docx",
  originalFilename = "",
  storedFilename = "",
  syllabusId = null,
  onConfirmAndUse,
  onCancel
}) {
  const [blueprint, setBlueprint] = useState(initialBlueprint || {
    template_name: "Extracted Template",
    institution: "Aarupadai Veedu Institute of Technology",
    course_code: "35021P28",
    course_title: "R Programming",
    programme: "B.E. Computer Science and Engineering",
    department: "Computer Science & Engineering",
    exam_name: "Internal Assessment",
    duration_minutes: 90,
    maximum_marks: 50,
    instructions: ["Answer all questions according to section rules."],
    sections: []
  });

  const [validation, setValidation] = useState(initialValidation || {
    is_valid: true,
    errors: [],
    warnings: [],
    calculated_total_marks: 50,
    target_maximum_marks: 50,
    reconciled: true
  });

  const [status, setStatus] = useState(extractionStatus);
  const [isValidating, setIsValidating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState("");
  const [showConfidenceDetails, setShowConfidenceDetails] = useState(false);
  const [saveTemplateName, setSaveTemplateName] = useState(blueprint.template_name || "Institution Examination Template");
  const [isSaveModalOpen, setIsSaveModalOpen] = useState(false);

  // Re-run validation
  const handleValidate = async () => {
    try {
      setIsValidating(true);
      const res = await api.validateExtractedBlueprint(blueprint, syllabusId);
      setValidation(res);
      setStatus(prev => prev === 'needs_verification' && res.is_valid ? 'faculty_corrected' : prev);
    } catch (err) {
      console.error("Validation error:", err);
    } finally {
      setIsValidating(false);
    }
  };

  // Modify Section Details
  const handleSectionChange = (secIdx, field, val) => {
    setBlueprint(prev => {
      const newSecs = [...prev.sections];
      newSecs[secIdx] = { ...newSecs[secIdx], [field]: val };
      return { ...prev, sections: newSecs };
    });
    setStatus('faculty_corrected');
  };

  // Modify Question Slot
  const handleQuestionChange = (secIdx, qIdx, field, val) => {
    setBlueprint(prev => {
      const newSecs = [...prev.sections];
      const newQs = [...newSecs[secIdx].questions];
      newQs[qIdx] = { ...newQs[qIdx], [field]: val };
      newSecs[secIdx] = { ...newSecs[secIdx], questions: newQs };
      return { ...prev, sections: newSecs };
    });
    setStatus('faculty_corrected');
  };

  // Add Question Slot
  const handleAddQuestionSlot = (secIdx) => {
    setBlueprint(prev => {
      const newSecs = [...prev.sections];
      const sec = newSecs[secIdx];
      const nextNum = String((sec.questions?.length || 0) + 1);
      const newSlot = {
        question_number: nextNum,
        or_pair_id: sec.or_choice ? `or_pair_${nextNum}` : null,
        question_types: ["short_answer"],
        unit: 1,
        co: "CO1",
        bloom_level: "L2",
        marks: sec.marks_per_question || 2
      };
      newSecs[secIdx] = {
        ...sec,
        question_count: (sec.questions?.length || 0) + 1,
        questions: [...(sec.questions || []), newSlot]
      };
      return { ...prev, sections: newSecs };
    });
    setStatus('faculty_corrected');
  };

  // Remove Question Slot
  const handleRemoveQuestionSlot = (secIdx, qIdx) => {
    setBlueprint(prev => {
      const newSecs = [...prev.sections];
      const newQs = newSecs[secIdx].questions.filter((_, idx) => idx !== qIdx);
      newSecs[secIdx] = {
        ...newSecs[secIdx],
        question_count: newQs.length,
        questions: newQs
      };
      return { ...prev, sections: newSecs };
    });
    setStatus('faculty_corrected');
  };

  // Save to Reusable Template Library
  const handleSaveToLibrary = async () => {
    try {
      setIsSaving(true);
      const payload = {
        template_name: saveTemplateName,
        institution: blueprint.institution,
        department: blueprint.department,
        programme: blueprint.programme,
        regulation: "2021 (Autonomous)",
        exam_name: blueprint.exam_name,
        exam_type: blueprint.exam_type || "Internal Assessment",
        maximum_marks: blueprint.maximum_marks,
        duration_minutes: blueprint.duration_minutes,
        academic_year: "2024-2025",
        course_code: blueprint.course_code,
        course_title: blueprint.course_title,
        blueprint: blueprint,
        original_filename: originalFilename,
        stored_filename: storedFilename,
        file_format: fileFormat,
        is_department_default: false,
        is_course_default: false
      };
      const res = await api.saveTemplateToLibrary(payload);
      setSaveSuccessMsg(`Template '${res.name}' saved to library successfully (Version 1)!`);
      setIsSaveModalOpen(false);
      setStatus('confirmed');
    } catch (err) {
      alert(err.message || 'Failed to save template to library.');
    } finally {
      setIsSaving(false);
    }
  };

  // Get status badge styling
  const getStatusBadge = () => {
    switch (status) {
      case 'confirmed':
        return <span className="px-2.5 py-1 text-xs font-bold bg-emerald-100 text-emerald-800 rounded-lg">Confirmed for Generation</span>;
      case 'faculty_corrected':
        return <span className="px-2.5 py-1 text-xs font-bold bg-blue-100 text-blue-800 rounded-lg">Faculty Corrected</span>;
      case 'needs_verification':
        return <span className="px-2.5 py-1 text-xs font-bold bg-amber-100 text-amber-800 rounded-lg">Needs Verification</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-bold bg-indigo-100 text-indigo-800 rounded-lg">Extracted from {fileFormat?.toUpperCase()}</span>;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-md p-6 space-y-6">
      
      {/* Top Header & Extraction Confidence */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-5">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h2 className="text-lg font-bold text-slate-900">
              Extracted Blueprint Review & Verification
            </h2>
            {getStatusBadge()}
          </div>
          <p className="text-xs text-slate-500">
            Verify extracted sections, question counts, marks, Course Outcomes (CO), and Bloom cognitive levels before question synthesis.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={handleValidate}
            disabled={isValidating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
          >
            <ShieldCheck className="w-4 h-4 text-blue-600" />
            <span>{isValidating ? "Validating..." : "Re-Validate"}</span>
          </button>

          <button
            type="button"
            onClick={() => setIsSaveModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-colors"
          >
            <Save className="w-4 h-4" />
            <span>Save to Library</span>
          </button>

          <button
            type="button"
            onClick={() => onConfirmAndUse(blueprint)}
            disabled={!validation.is_valid}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" />
            <span>Confirm & Use for Generation</span>
          </button>
        </div>
      </div>

      {saveSuccessMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl flex items-center justify-between">
          <span className="font-semibold">{saveSuccessMsg}</span>
          <button onClick={() => setSaveSuccessMsg("")} className="text-emerald-600 hover:underline">Dismiss</button>
        </div>
      )}

      {/* Validation Banner */}
      {!validation.is_valid ? (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-2">
          <div className="flex items-center gap-2 text-rose-800 font-bold text-xs">
            <XCircle className="w-4 h-4 text-rose-600" />
            <span>Blueprint Validation Errors (Generation Blocked Until Reconciled)</span>
          </div>
          <ul className="list-disc list-inside text-xs text-rose-700 space-y-1">
            {validation.errors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-semibold">
              Blueprint Reconciled: Total calculated marks ({validation.calculated_total_marks}) match target maximum marks ({validation.target_maximum_marks}).
            </span>
          </div>
          <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-200 text-emerald-900 rounded-md">
            100% RECONCILED
          </span>
        </div>
      )}

      {validation.warnings && validation.warnings.length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 space-y-1">
          <div className="flex items-center gap-1.5 font-bold">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Advisory Warnings (Non-Blocking):</span>
          </div>
          <ul className="list-disc list-inside text-[11px] text-amber-700 pl-1 space-y-0.5">
            {validation.warnings.map((warn, idx) => (
              <li key={idx}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Confidence Indicators (Specification B5) */}
      {confidenceScores && (
        <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-800">Extraction Confidence:</span>
              <span className="font-extrabold text-blue-700">
                {Math.round((confidenceScores.overall || 0.8) * 100)}%
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowConfidenceDetails(!showConfidenceDetails)}
              className="text-blue-600 hover:text-blue-800 font-semibold text-[11px] flex items-center gap-1"
            >
              <span>{showConfidenceDetails ? "Hide Field Scores" : "View Field Breakdown"}</span>
              {showConfidenceDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>

          {showConfidenceDetails && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-200 text-[11px]">
              <div>Institution: <strong>{Math.round(confidenceScores.institution * 100)}%</strong></div>
              <div>Course Info: <strong>{Math.round(confidenceScores.course_information * 100)}%</strong></div>
              <div>Sections: <strong>{Math.round(confidenceScores.section_names * 100)}%</strong></div>
              <div>Question Nos: <strong>{Math.round(confidenceScores.question_numbering * 100)}%</strong></div>
              <div>Marks: <strong>{Math.round(confidenceScores.marks * 100)}%</strong></div>
              <div>Course Outcomes: <strong>{Math.round(confidenceScores.course_outcomes * 100)}%</strong></div>
              <div>Bloom Levels: <strong>{Math.round(confidenceScores.bloom_levels * 100)}%</strong></div>
              <div>OR Choices: <strong>{Math.round(confidenceScores.or_choices * 100)}%</strong></div>
            </div>
          )}
        </div>
      )}

      {/* Examination Header Metadata Form */}
      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
        <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
          <FileText className="w-4 h-4 text-indigo-600" />
          Examination Header & Metadata
        </h3>
        
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Institution Name</label>
            <input
              type="text"
              value={blueprint.institution}
              onChange={(e) => {
                setBlueprint({ ...blueprint, institution: e.target.value });
                setStatus('faculty_corrected');
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Course Code</label>
            <input
              type="text"
              value={blueprint.course_code}
              onChange={(e) => {
                setBlueprint({ ...blueprint, course_code: e.target.value });
                setStatus('faculty_corrected');
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Course Title</label>
            <input
              type="text"
              value={blueprint.course_title}
              onChange={(e) => {
                setBlueprint({ ...blueprint, course_title: e.target.value });
                setStatus('faculty_corrected');
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Exam Name</label>
            <input
              type="text"
              value={blueprint.exam_name}
              onChange={(e) => {
                setBlueprint({ ...blueprint, exam_name: e.target.value });
                setStatus('faculty_corrected');
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Maximum Marks</label>
            <input
              type="number"
              value={blueprint.maximum_marks}
              onChange={(e) => {
                setBlueprint({ ...blueprint, maximum_marks: parseInt(e.target.value, 10) || 0 });
                setStatus('faculty_corrected');
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white font-bold"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 mb-1">Duration (Minutes)</label>
            <input
              type="number"
              value={blueprint.duration_minutes}
              onChange={(e) => {
                setBlueprint({ ...blueprint, duration_minutes: parseInt(e.target.value, 10) || 0 });
                setStatus('faculty_corrected');
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white"
            />
          </div>
        </div>
      </div>

      {/* Sections and Question Slots */}
      <div className="space-y-6">
        {blueprint.sections?.map((sec, secIdx) => (
          <div key={secIdx} className="p-4 bg-slate-50/70 border border-slate-200 rounded-xl space-y-3">
            
            {/* Section Header Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200/70 pb-3">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={sec.section_name}
                  onChange={(e) => handleSectionChange(secIdx, "section_name", e.target.value)}
                  className="font-bold text-sm text-slate-900 bg-white px-2 py-1 rounded border border-slate-300 w-32"
                />
                <span className="text-xs text-slate-500 font-medium">
                  {sec.questions?.length || 0} Questions • Total {sec.section_total} Marks
                </span>
                {sec.or_choice && (
                  <span className="text-[10px] font-bold px-2 py-0.5 bg-amber-100 text-amber-800 rounded border border-amber-200">
                    Internal Choice (OR)
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={sec.answer_rule}
                  placeholder="Answer rule (e.g. Answer all questions)"
                  onChange={(e) => handleSectionChange(secIdx, "answer_rule", e.target.value)}
                  className="text-xs text-slate-700 bg-white px-2 py-1 rounded border border-slate-300 w-56 truncate"
                />
                <button
                  type="button"
                  onClick={() => handleAddQuestionSlot(secIdx)}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg border border-blue-200"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Slot</span>
                </button>
              </div>
            </div>

            {/* Questions Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-200 text-[11px] font-bold">
                    <th className="pb-2 pl-1 w-16">Q.No</th>
                    <th className="pb-2 w-28">OR Pair</th>
                    <th className="pb-2 w-24">Marks</th>
                    <th className="pb-2 w-20">Unit</th>
                    <th className="pb-2 w-24">CO</th>
                    <th className="pb-2 w-24">Bloom</th>
                    <th className="pb-2">Question Types</th>
                    <th className="pb-2 text-right pr-1 w-12">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200/60">
                  {sec.questions?.map((q, qIdx) => (
                    <tr key={qIdx} className="hover:bg-slate-100/50">
                      
                      {/* Q.No */}
                      <td className="py-2 pl-1 font-semibold text-slate-800">
                        <input
                          type="text"
                          value={q.question_number}
                          onChange={(e) => handleQuestionChange(secIdx, qIdx, "question_number", e.target.value)}
                          className="w-14 px-1.5 py-1 text-xs rounded border border-slate-300 bg-white font-bold text-center"
                        />
                      </td>

                      {/* OR Pair */}
                      <td className="py-2">
                        <input
                          type="text"
                          value={q.or_pair_id || ""}
                          placeholder="None"
                          onChange={(e) => handleQuestionChange(secIdx, qIdx, "or_pair_id", e.target.value || null)}
                          className="w-24 px-1.5 py-1 text-[11px] rounded border border-slate-300 bg-white"
                        />
                      </td>

                      {/* Marks */}
                      <td className="py-2">
                        <input
                          type="number"
                          value={q.marks}
                          onChange={(e) => handleQuestionChange(secIdx, qIdx, "marks", parseInt(e.target.value, 10) || 0)}
                          className="w-16 px-1.5 py-1 text-xs rounded border border-slate-300 bg-white font-bold text-center"
                        />
                      </td>

                      {/* Unit */}
                      <td className="py-2">
                        <select
                          value={q.unit || 1}
                          onChange={(e) => handleQuestionChange(secIdx, qIdx, "unit", parseInt(e.target.value, 10))}
                          className="w-16 px-1.5 py-1 text-xs rounded border border-slate-300 bg-white"
                        >
                          {[1, 2, 3, 4, 5].map(u => (
                            <option key={u} value={u}>U{u}</option>
                          ))}
                        </select>
                      </td>

                      {/* Course Outcome */}
                      <td className="py-2">
                        <select
                          value={q.co || "CO1"}
                          onChange={(e) => handleQuestionChange(secIdx, qIdx, "co", e.target.value)}
                          className="w-20 px-1.5 py-1 text-xs rounded border border-slate-300 bg-white font-semibold text-blue-700"
                        >
                          {ALL_CO_LEVELS.map(co => (
                            <option key={co} value={co}>{co}</option>
                          ))}
                        </select>
                      </td>

                      {/* Bloom Level */}
                      <td className="py-2">
                        <select
                          value={q.bloom_level || "L2"}
                          onChange={(e) => handleQuestionChange(secIdx, qIdx, "bloom_level", e.target.value)}
                          className="w-20 px-1.5 py-1 text-xs rounded border border-slate-300 bg-white font-semibold text-indigo-700"
                        >
                          {ALL_BLOOM_LEVELS.map(bl => (
                            <option key={bl} value={bl}>{bl}</option>
                          ))}
                        </select>
                      </td>

                      {/* Question Types */}
                      <td className="py-2">
                        <div className="flex flex-wrap items-center gap-1">
                          {(q.question_types || ["short_answer"]).map((t, tIdx) => (
                            <span key={tIdx} className="px-2 py-0.5 text-[10px] font-bold bg-blue-100 text-blue-800 rounded uppercase">
                              {t}
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* Action */}
                      <td className="py-2 text-right pr-1">
                        <button
                          type="button"
                          onClick={() => handleRemoveQuestionSlot(secIdx, qIdx)}
                          className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                          title="Remove Slot"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

          </div>
        ))}
      </div>

      {/* Save Modal */}
      {isSaveModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Save to Template Library</h3>
            <p className="text-xs text-slate-500">
              Save this confirmed blueprint structure as a reusable institutional template for future examinations.
            </p>
            <div>
              <label className="block text-[11px] font-semibold text-slate-700 mb-1">Template Name</label>
              <input
                type="text"
                value={saveTemplateName}
                onChange={(e) => setSaveTemplateName(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                placeholder="e.g. AVIT Computer Science Internal Assessment Template"
              />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsSaveModalOpen(false)}
                className="px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveToLibrary}
                disabled={isSaving || !saveTemplateName.trim()}
                className="px-4 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Save Template"}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
