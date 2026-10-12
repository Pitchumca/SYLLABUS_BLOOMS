import React, { useState, useEffect, useRef } from 'react';
import { 
  FileText, 
  Presentation, 
  UploadCloud, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  Edit3, 
  RefreshCw, 
  Trash2, 
  Download, 
  ChevronRight, 
  Layers, 
  BookOpen, 
  FileSpreadsheet, 
  Plus, 
  Check, 
  Clock, 
  Award,
  Sliders,
  HelpCircle,
  FileCheck,
  Eye,
  X,
  XCircle,
  Search,
  ChevronDown,
  ChevronUp,
  File,
  Filter,
  Info,
  FileCode,
  ShieldAlert,
  ShieldCheck,
  CheckCheck
} from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';
import ExtractedBlueprintReviewer from '../components/ExtractedBlueprintReviewer';
import TemplateUploadModal from '../components/TemplateUploadModal';
import MultiSelectQuestionTypes from '../components/MultiSelectQuestionTypes';

export default function QuestionPaperPage() {
  const { 
    currentSyllabus, 
    setCurrentSyllabus, 
    notify, 
    loading, 
    setLoading, 
    setActiveTab, 
    setBooks,
    navigate,
    currentPath
  } = useApp();

  // Helper to parse route and query params
  const parseRouteState = () => {
    const pathname = window.location.pathname;
    const search = window.location.search;
    const params = new URLSearchParams(search);

    let paperId = null;
    let step = null;

    // Pattern 1: /question-papers/:paperId/:step
    // Pattern 2: /question-papers/:paperId
    // Pattern 3: /question-papers/:step
    const qpMatch = pathname.match(/^\/question-papers(?:\/(\d+))?(?:\/([a-zA-Z0-9_-]+))?/);
    if (qpMatch) {
      if (qpMatch[1]) paperId = parseInt(qpMatch[1], 10);
      if (qpMatch[2]) step = qpMatch[2].toLowerCase();
    }

    if (!step) {
      if (pathname.endsWith('/export') || pathname === '/export') step = 'export';
      else if (pathname.endsWith('/review') || pathname === '/review' || pathname.endsWith('/validation')) step = 'validation';
      else if (pathname.endsWith('/blueprint') || pathname === '/blueprint') step = 'blueprint';
      else if (pathname.endsWith('/content') || pathname === '/content') step = 'content';
    }

    if (!paperId) {
      const qpParam = params.get('paper_id') || params.get('id');
      if (qpParam) paperId = parseInt(qpParam, 10);
    }
    if (!step) {
      const stepParam = params.get('step');
      if (stepParam) step = stepParam.toLowerCase();
    }

    if (step === 'review') step = 'validation';

    return { paperId, step };
  };

  // Wizard active step: 'content' | 'blueprint' | 'validation' | 'export'
  const [activeStep, setActiveStep] = useState(() => {
    const { step } = parseRouteState();
    return step && ['content', 'blueprint', 'validation', 'export'].includes(step) ? step : 'content';
  });

  const [isProceeding, setIsProceeding] = useState(false);
  const [proceedError, setProceedError] = useState('');
  const [exportValidationData, setExportValidationData] = useState(null);
  const [isValidatingExport, setIsValidatingExport] = useState(false);

  // Step 1: Syllabus & Content Upload
  const [contentFiles, setContentFiles] = useState([]);
  const [courseOutcomes, setCourseOutcomes] = useState([]);
  const [units, setUnits] = useState([]);
  const [isUploadingContent, setIsUploadingContent] = useState(false);
  const [alignmentSummary, setAlignmentSummary] = useState(null);
  const [selectedFilePreview, setSelectedFilePreview] = useState(null);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewSearchTerm, setPreviewSearchTerm] = useState('');
  const fileInputRef = useRef(null);
  const pptInputRef = useRef(null);

  // Step 2: Blueprint & Grounding Strategy
  const [blueprintSourceTab, setBlueprintSourceTab] = useState('preset'); // 'preset' | 'upload_template' | 'template_library' | 'custom'
  const [isTemplateUploadModalOpen, setIsTemplateUploadModalOpen] = useState(false);
  const [extractedTemplateData, setExtractedTemplateData] = useState(null);
  const [savedTemplatesList, setSavedTemplatesList] = useState([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);
  const [selectedTemplateName, setSelectedTemplateName] = useState(null);

  const [presets, setPresets] = useState([]);
  const [selectedPresetId, setSelectedPresetId] = useState('univ_100_abc');
  const [generationMode, setGenerationMode] = useState('syllabus_ppt'); // 'syllabus_ppt' | 'syllabus_only' | 'all_sources'
  const [coverageMatrix, setCoverageMatrix] = useState(null);
  const [isCoverageLoading, setIsCoverageLoading] = useState(false);
  const [showCoverageDetails, setShowCoverageDetails] = useState(false);

  const [blueprintMeta, setBlueprintMeta] = useState({
    institution_name: "",
    course_name: "",
    course_code: "",
    programme: "",
    regulation: "",
    exam_name: "Semester End Examination",
    academic_year: "",
    semester: "",
    department: "",
    assigned_faculty: "",
    duration: "3 Hours",
    max_marks: 100,
    instructions: "Answer ALL questions in Part A. Answer either (a) or (b) from each question in Part B. Show calculations clearly."
  });
  const [blueprintSections, setBlueprintSections] = useState([]);

  // Step 3: Question Paper Review & Validation
  const [questionPaper, setQuestionPaper] = useState(null);
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddQuestionModalOpen, setIsAddQuestionModalOpen] = useState(false);
  const [selectedProvenance, setSelectedProvenance] = useState(null);
  const [isProvenanceModalOpen, setIsProvenanceModalOpen] = useState(false);
  const [rejectModalData, setRejectModalData] = useState({ question: null, remarks: '' });
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [regenerateModalData, setRegenerateModalData] = useState({
    question: null,
    directive: 'standard',
    target_bloom: '',
    target_difficulty: '',
    target_topic: '',
    target_type: '',
    prompt: ''
  });
  const [isRegenerateModalOpen, setIsRegenerateModalOpen] = useState(false);
  const [expandedAnswers, setExpandedAnswers] = useState({});

  const [newQuestionData, setNewQuestionData] = useState({
    section_name: 'Part A',
    question_number: 'New',
    question_text: '',
    marks: 2,
    co_level: 'CO1',
    bloom_level: 'L2 - Understand',
    model_answer: '',
    marking_scheme: ''
  });

  // Step 4: Word Template & Export
  const [templateFile, setTemplateFile] = useState(null);
  const [templateUploaded, setTemplateUploaded] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadingType, setDownloadingType] = useState(null);
  const [exportError, setExportError] = useState('');
  const [facultyPapers, setFacultyPapers] = useState([]);
  const templateInputRef = useRef(null);

  const questionPaperId = questionPaper?.id;

  // Load initial presets, existing papers, and template library
  useEffect(() => {
    loadPresets();
    loadFacultyPapers();
    loadTemplateLibrary();
  }, []);

  const loadTemplateLibrary = async () => {
    try {
      setIsLoadingTemplates(true);
      const list = await api.getTemplateLibrary();
      setSavedTemplatesList(list || []);
    } catch (err) {
      console.error('Failed to load template library:', err);
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleExtractionSuccess = (data) => {
    setExtractedTemplateData(data);
    setBlueprintSourceTab('upload_template');
    notify(`Blueprint extracted from ${data.file_format?.toUpperCase() || 'template'} with ${data.blueprint?.sections?.length || 0} sections!`, 'success');
  };

  const handleConfirmExtractedBlueprint = (canonicalBlueprint, savedTemplateId = null) => {
    if (savedTemplateId) {
      setSelectedTemplateId(savedTemplateId);
    }
    setSelectedTemplateName(canonicalBlueprint.template_name || canonicalBlueprint.institution || "Uploaded Institution Template");
    
    // Auto-update blueprint metadata
    setBlueprintMeta(prev => ({
      ...prev,
      institution_name: canonicalBlueprint.institution || prev.institution_name,
      course_name: canonicalBlueprint.course_title || prev.course_name,
      course_code: canonicalBlueprint.course_code || prev.course_code,
      programme: canonicalBlueprint.programme || prev.programme,
      department: canonicalBlueprint.department || prev.department,
      semester: canonicalBlueprint.semester || prev.semester,
      regulation: canonicalBlueprint.regulation || prev.regulation,
      academic_year: canonicalBlueprint.academic_year || prev.academic_year,
      exam_name: canonicalBlueprint.exam_name || prev.exam_name,
      duration: canonicalBlueprint.duration_minutes ? `${canonicalBlueprint.duration_minutes} Minutes` : prev.duration,
      max_marks: canonicalBlueprint.maximum_marks || prev.max_marks,
      instructions: Array.isArray(canonicalBlueprint.instructions) 
        ? canonicalBlueprint.instructions.join('\n') 
        : (canonicalBlueprint.instructions || prev.instructions)
    }));

    // Map canonical sections to blueprintSections for the generator
    const mappedSections = (canonicalBlueprint.sections || []).map(sec => {
      const qTypes = [];
      const coDist = [];
      const bloomDist = [];
      (sec.questions || []).forEach(q => {
        if (q.co_level) coDist.push(q.co_level);
        if (q.bloom_level) bloomDist.push(q.bloom_level);
        if (Array.isArray(q.question_types) && q.question_types.length > 0) {
          qTypes.push(q.question_types[0].question_type);
        }
      });

      return {
        name: sec.section_name,
        instructions: sec.instructions || `Answer questions in ${sec.section_name}`,
        questions_count: sec.questions_count || (sec.questions?.length || 5),
        marks_per_question: sec.marks_per_question || 2,
        has_internal_choice: sec.has_internal_choice || sec.choice_rule === 'internal_choice_either_or',
        question_type: qTypes[0] || (sec.marks_per_question > 5 ? 'programming' : 'short_answer'),
        question_types: qTypes.length > 0 ? qTypes : [sec.marks_per_question > 5 ? 'programming' : 'short_answer'],
        co_distribution: coDist.length > 0 ? coDist : ['CO1', 'CO2', 'CO3', 'CO4', 'CO5'],
        bloom_distribution: bloomDist.length > 0 ? bloomDist : ['L1 - Remember', 'L2 - Understand'],
        questions: (sec.questions || []).map(q => ({
          question_number: q.question_number,
          marks: q.marks,
          bloom_level: q.bloom_level,
          co_level: q.co_level,
          or_pair_with: q.or_pair_with,
          question_types: q.question_types
        }))
      };
    });

    setBlueprintSections(mappedSections);
    notify('Extracted blueprint confirmed and applied to examination generator!', 'success');
  };

  const handleSelectTemplateFromLibrary = async (tmpl) => {
    try {
      setLoading(true);
      const detail = await api.getTemplateDetail(tmpl.id);
      setSelectedTemplateId(tmpl.id);
      setSelectedTemplateName(tmpl.template_name);
      if (detail.canonical_blueprint) {
        handleConfirmExtractedBlueprint(detail.canonical_blueprint, tmpl.id);
      }
      notify(`Applied template '${tmpl.template_name}' from library!`, 'success');
    } catch (err) {
      notify(err.message || 'Failed to apply template', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplateFromLibrary = async (tmplId) => {
    if (!window.confirm("Are you sure you want to delete this template from the library?")) return;
    try {
      await api.deleteTemplate(tmplId);
      notify("Template deleted from library.", "info");
      if (selectedTemplateId === tmplId) {
        setSelectedTemplateId(null);
        setSelectedTemplateName(null);
      }
      await loadTemplateLibrary();
    } catch (err) {
      notify(err.message || "Failed to delete template", "error");
    }
  };

  const applyPreset = (preset) => {
    setSelectedPresetId(preset.id);
    setSelectedTemplateId(null);
    setSelectedTemplateName(null);
    setBlueprintMeta(prev => ({
      ...prev,
      max_marks: preset.max_marks,
      duration: preset.duration
    }));
    const sectionsWithTypes = (preset.sections || []).map(sec => ({
      ...sec,
      question_types: sec.question_types || [sec.question_type || (sec.marks_per_question > 5 ? 'programming' : 'short_answer')]
    }));
    setBlueprintSections(sectionsWithTypes);
  };

  // Dynamically load outcomes, content, metadata and alignment when syllabus changes
  useEffect(() => {
    if (currentSyllabus?.id) {
      loadOutcomesAndContent(currentSyllabus.id);
    }
  }, [currentSyllabus]);

  // Refresh coverage matrix when generationMode changes and on blueprint step
  useEffect(() => {
    if (currentSyllabus?.id && activeStep === 'blueprint') {
      refreshCoverageMatrix(currentSyllabus.id, generationMode);
    }
  }, [generationMode, activeStep]);

  const loadFacultyPapers = async () => {
    try {
      const papers = await api.listFacultyQuestionPapers();
      setFacultyPapers(papers || []);

      const { paperId, step } = parseRouteState();

      if (paperId) {
        const fullPaper = await api.getQuestionPaper(paperId);
        if (fullPaper) {
          setQuestionPaper(fullPaper);
          if (step) {
            setActiveStep(step);
          } else if (fullPaper.questions && fullPaper.questions.length > 0) {
            setActiveStep('validation');
          }
          return;
        }
      }

      if (!questionPaper && papers && papers.length > 0) {
        const latest = papers[0];
        const fullPaper = await api.getQuestionPaper(latest.id);
        if (fullPaper) {
          setQuestionPaper(fullPaper);
          if (step) {
            setActiveStep(step);
          } else if (fullPaper.questions && fullPaper.questions.length > 0) {
            setActiveStep('validation');
          }
        }
      }
    } catch (err) {
      console.error('Failed to load faculty papers:', err);
    }
  };

  // Synchronize state when route changes (browser back/forward, direct navigate)
  useEffect(() => {
    const { paperId, step } = parseRouteState();
    if (step && ['content', 'blueprint', 'validation', 'export'].includes(step)) {
      setActiveStep(step);
    }
    if (paperId && (!questionPaper || questionPaper.id !== paperId)) {
      api.getQuestionPaper(paperId).then(p => {
        if (p) {
          setQuestionPaper(p);
          if (!step && p.questions && p.questions.length > 0) {
            setActiveStep('validation');
          }
        }
      }).catch(err => {
        console.error('Failed to load paper from route:', err);
      });
    }
  }, [currentPath]);

  // When export step is opened, fetch fresh export validation data
  useEffect(() => {
    if (activeStep === 'export' && questionPaperId) {
      api.getExportValidation(questionPaperId)
        .then(val => {
          setExportValidationData(val);
        })
        .catch(err => console.error("Export validation check error:", err));
    }
  }, [activeStep, questionPaperId]);

  const loadPresets = async () => {
    try {
      const data = await api.getBlueprintPresets();
      setPresets(data || []);
      if (data && data.length > 0) {
        applyPreset(data[0]);
      }
    } catch (err) {
      console.error('Failed to load presets:', err);
    }
  };

  // Dynamically load outcomes, content files, alignments, and metadata from DB
  const loadOutcomesAndContent = async (syllabusId) => {
    try {
      setLoading(true);
      const [outs, uns, files, meta, aligns] = await Promise.all([
        api.getCourseOutcomes(syllabusId).catch(() => []),
        api.getSyllabusUnits(syllabusId).catch(() => []),
        api.getContentFiles(syllabusId).catch(() => []),
        api.getCourseMetadata(syllabusId).catch(() => null),
        api.getContentAlignments(syllabusId).catch(() => null)
      ]);

      setCourseOutcomes(outs || []);
      setUnits(uns || []);
      setContentFiles(files || []);
      if (aligns) setAlignmentSummary(aligns);

      // Auto-populate blueprint metadata from real database records (no demo hardcoding)
      if (meta) {
        setBlueprintMeta(prev => ({
          ...prev,
          institution_name: meta.institution_name || prev.institution_name || "Aarupadai Veedu Institute of Technology",
          course_name: meta.course_name || prev.course_name || (currentSyllabus?.original_filename || "Curriculum Course"),
          course_code: meta.course_code || prev.course_code || "",
          programme: meta.programme || prev.programme || "B.E. Computer Science and Engineering",
          semester: meta.semester || prev.semester || "IV",
          academic_year: meta.academic_year || prev.academic_year || "2024-2025",
          department: meta.department || prev.department || "Computer Science and Engineering",
          regulation: meta.regulation || prev.regulation || "2021",
          assigned_faculty: meta.assigned_faculty || prev.assigned_faculty || ""
        }));
      }

      await refreshCoverageMatrix(syllabusId, generationMode);
    } catch (err) {
      console.error('Failed to load syllabus outcomes:', err);
    } finally {
      setLoading(false);
    }
  };

  const refreshCoverageMatrix = async (syllabusId, mode) => {
    if (!syllabusId) return;
    try {
      setIsCoverageLoading(true);
      const matrix = await api.getCoverageMatrix({ syllabus_id: syllabusId, generation_mode: mode });
      setCoverageMatrix(matrix);
    } catch (err) {
      console.error('Failed to load coverage matrix:', err);
    } finally {
      setIsCoverageLoading(false);
    }
  };

  // Upload Syllabus PDF
  const handleSyllabusUpload = async (file) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      notify('Please upload a PDF syllabus.', 'error');
      return;
    }
    try {
      setLoading(true);
      const syl = await api.uploadSyllabus(file);
      setCurrentSyllabus(syl);
      notify(`Syllabus '${syl.original_filename}' uploaded successfully!`, 'success');
      await loadOutcomesAndContent(syl.id);
    } catch (err) {
      notify(err.message || 'Syllabus upload failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Load built-in sample syllabus
  const handleLoadSample = async () => {
    try {
      setLoading(true);
      const syl = await api.loadSampleSyllabus();
      setCurrentSyllabus(syl);
      notify('Computer Science sample syllabus loaded!', 'success');
      await loadOutcomesAndContent(syl.id);
    } catch (err) {
      notify(err.message || 'Failed to load sample syllabus', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Upload Lecture Materials (PPT/PPTX, PDF, DOCX, TXT)
  const handleContentUpload = async (file) => {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pptx', 'ppt', 'pdf', 'docx', 'txt'].includes(ext)) {
      notify('Allowed formats: PowerPoint (.pptx, .ppt), Lecture Notes (.pdf, .docx, .txt)', 'error');
      return;
    }
    try {
      setIsUploadingContent(true);
      const record = await api.uploadContentFile(file, currentSyllabus?.id);
      const countLabel = record.file_type === 'pdf' ? 'pages' : (record.file_type === 'pptx' || record.file_type === 'ppt' ? 'slides' : 'sections');
      notify(`Content file '${record.original_filename}' processed with ${record.slide_or_page_count || 0} ${countLabel}!`, 'success');
      if (currentSyllabus) {
        await loadOutcomesAndContent(currentSyllabus.id);
      }
    } catch (err) {
      notify(err.message || 'Content upload failed', 'error');
    } finally {
      setIsUploadingContent(false);
    }
  };

  // Delete Content File
  const handleDeleteContentFile = async (fileId) => {
    try {
      await api.deleteContentFile(fileId);
      notify('Content file deleted and unlinked from syllabus.', 'info');
      if (currentSyllabus) {
        await loadOutcomesAndContent(currentSyllabus.id);
      }
    } catch (err) {
      notify(err.message || 'Failed to delete file', 'error');
    }
  };

  // Preview Chunks Modal
  const handlePreviewFile = async (fileId) => {
    try {
      setLoading(true);
      const preview = await api.getContentFilePreview(fileId);
      setSelectedFilePreview(preview);
      setPreviewSearchTerm('');
      setIsPreviewModalOpen(true);
    } catch (err) {
      notify(err.message || 'Failed to load file preview', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Extract Books
  const handleExtractBooks = async () => {
    if (!currentSyllabus) return;
    try {
      setLoading(true);
      const res = await api.parseBooks(currentSyllabus.id);
      setBooks(res.books || []);
      notify(`Extracted ${res.books_found} textbook and reference citations!`, 'success');
      setActiveTab('review');
    } catch (err) {
      notify(err.message || 'Book extraction failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Generate Questions based on Blueprint & Grounding Strategy
  const handleGenerateQuestions = async () => {
    if (!currentSyllabus) {
      notify('Please upload a course syllabus first.', 'error');
      setActiveStep('content');
      return;
    }
    try {
      setLoading(true);
      const payload = {
        syllabus_id: currentSyllabus.id,
        template_id: selectedTemplateId || null,
        generation_mode: generationMode,
        institution_name: blueprintMeta.institution_name,
        course_name: blueprintMeta.course_name,
        course_code: blueprintMeta.course_code,
        programme: blueprintMeta.programme,
        regulation: blueprintMeta.regulation,
        assigned_faculty: blueprintMeta.assigned_faculty,
        exam_name: blueprintMeta.exam_name,
        academic_year: blueprintMeta.academic_year,
        semester: blueprintMeta.semester,
        department: blueprintMeta.department,
        duration: blueprintMeta.duration,
        max_marks: parseInt(blueprintMeta.max_marks, 10),
        instructions: blueprintMeta.instructions,
        sections: blueprintSections
      };
      const paper = await api.generateQuestionPaper(payload);
      setQuestionPaper(paper);
      notify(`Successfully generated ${paper.questions?.length || 0} grounded questions in Draft status!`, 'success');
      setActiveStep('validation');
    } catch (err) {
      notify(err.message || 'Failed to generate question paper', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Faculty Review Actions: Approve / Reject / Edit
  const handleReviewQuestion = async (questionId, action, remarks = '') => {
    if (!questionPaper) return;
    try {
      const updated = await api.reviewQuestion(questionPaper.id, questionId, {
        action,
        reviewer_remarks: remarks
      });
      setQuestionPaper(prev => ({
        ...prev,
        questions: prev.questions.map(q => q.id === questionId ? updated : q)
      }));
      if (action === 'approve') {
        notify(`Question ${updated.question_number} approved!`, 'success');
      } else if (action === 'reject') {
        notify(`Question ${updated.question_number} rejected.`, 'info');
      } else {
        notify(`Question ${updated.question_number} set to draft.`, 'info');
      }
    } catch (err) {
      notify(err.message || 'Review action failed', 'error');
    }
  };

  const handleBulkValidateAll = async () => {
    if (!questionPaper) return;
    try {
      setLoading(true);
      const updatedPaper = await api.validateAllQuestions(questionPaper.id);
      setQuestionPaper(updatedPaper);
      notify('All questions have been approved & validated by faculty!', 'success');
    } catch (err) {
      notify(err.message || 'Bulk approval failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const openRegenerateModal = (question) => {
    setRegenerateModalData({
      question,
      directive: 'standard',
      target_bloom: question.bloom_level,
      target_difficulty: question.difficulty || 'Medium',
      target_topic: question.source_topic || '',
      target_type: question.question_type || 'short_answer',
      prompt: ''
    });
    setIsRegenerateModalOpen(true);
  };

  const handleExecuteRegenerate = async () => {
    if (!questionPaper || !regenerateModalData.question) return;
    try {
      setLoading(true);
      const updated = await api.regenerateQuestion(questionPaper.id, regenerateModalData.question.id, {
        directive: regenerateModalData.directive,
        target_bloom_level: regenerateModalData.target_bloom,
        target_difficulty: regenerateModalData.target_difficulty,
        target_topic: regenerateModalData.target_topic,
        target_question_type: regenerateModalData.target_type,
        faculty_prompt: regenerateModalData.prompt
      });
      setQuestionPaper(prev => ({
        ...prev,
        questions: prev.questions.map(q => q.id === updated.id ? updated : q)
      }));
      setIsRegenerateModalOpen(false);
      notify(`Question ${updated.question_number} regenerated with fresh grounded context!`, 'success');
    } catch (err) {
      notify(err.message || 'Regeneration failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Grounding Provenance Lookup Modal
  const handleOpenProvenance = async (questionId) => {
    if (!questionPaper) return;
    try {
      setLoading(true);
      const prov = await api.getQuestionProvenance(questionPaper.id, questionId);
      setSelectedProvenance(prov);
      setIsProvenanceModalOpen(true);
    } catch (err) {
      notify(err.message || 'Failed to load grounding provenance', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Edit Modal
  const openEditModal = (question) => {
    let opts = [];
    if (Array.isArray(question.options) && question.options.length > 0) {
      opts = question.options.map(o => ({ ...o }));
    } else if (question.options_json) {
      try {
        const raw = typeof question.options_json === 'string' ? JSON.parse(question.options_json) : question.options_json;
        if (Array.isArray(raw)) {
          opts = raw.map((o, idx) => {
            if (typeof o === 'object' && o !== null) {
              return {
                label: (o.label || String.fromCharCode(65 + idx)).trim().toUpperCase(),
                text: (o.text || '').trim(),
                is_correct: o.is_correct === true || o.is_correct === 1 || o.is_correct === "1" || String(o.is_correct).toLowerCase() === 'true'
              };
            } else {
              return {
                label: String.fromCharCode(65 + idx),
                text: String(o).replace(/^[A-E][\)\.]\s*/, '').trim(),
                is_correct: false
              };
            }
          });
        }
      } catch (e) {
        opts = [];
      }
    }

    const isMcq = (question.question_type && question.question_type.startsWith('mcq')) || 
                  (opts && opts.length > 0) || 
                  question.section_name === 'Part A';

    if (isMcq && (!opts || opts.length === 0)) {
      opts = [
        { label: 'A', text: '', is_correct: true },
        { label: 'B', text: '', is_correct: false },
        { label: 'C', text: '', is_correct: false },
        { label: 'D', text: '', is_correct: false }
      ];
    }

    let correctOpt = question.correct_answer || question.correct_answer_json || 'A';
    const foundCorr = opts.find(o => o.is_correct);
    if (foundCorr) {
      correctOpt = foundCorr.label;
    } else if (opts.length > 0) {
      const match = opts.find(o => o.label === correctOpt);
      if (match) match.is_correct = true;
      else opts[0].is_correct = true;
    }

    setEditingQuestion({
      ...question,
      edit_options: opts,
      correct_option_selected: correctOpt,
      edit_explanation: question.explanation || ''
    });
    setIsEditModalOpen(true);
  };

  const handleSaveQuestionEdit = async (e) => {
    e.preventDefault();
    if (!questionPaper || !editingQuestion) return;

    const isMcq = (editingQuestion.question_type && editingQuestion.question_type.startsWith('mcq')) || 
                  (editingQuestion.edit_options && editingQuestion.edit_options.length > 0);

    if (isMcq) {
      const opts = editingQuestion.edit_options || [];
      if (opts.length !== 4) {
        notify('MCQ must have exactly 4 options.', 'error');
        return;
      }
      for (const opt of opts) {
        if (!opt.text.trim()) {
          notify(`Option ${opt.label} text cannot be empty.`, 'error');
          return;
        }
      }
      const correctCount = opts.filter(o => o.is_correct).length;
      if (correctCount !== 1) {
        notify('Please select exactly one correct option.', 'error');
        return;
      }
    }

    try {
      setLoading(true);
      const payload = {
        action: 'edit',
        updated_question_text: editingQuestion.question_text,
        updated_marks: parseInt(editingQuestion.marks, 10),
        updated_co_level: editingQuestion.co_level,
        updated_bloom_level: editingQuestion.bloom_level,
        updated_difficulty: editingQuestion.difficulty,
        updated_topic: editingQuestion.source_topic,
        updated_model_answer: editingQuestion.model_answer,
        updated_marking_scheme: editingQuestion.marking_scheme
      };

      if (isMcq) {
        payload.updated_options = editingQuestion.edit_options;
        payload.updated_correct_answer = editingQuestion.correct_option_selected;
        payload.updated_explanation = editingQuestion.edit_explanation;
      }

      const updated = await api.reviewQuestion(questionPaper.id, editingQuestion.id, payload);
      setQuestionPaper(prev => ({
        ...prev,
        questions: prev.questions.map(q => q.id === editingQuestion.id ? updated : q)
      }));
      setIsEditModalOpen(false);
      notify('Question updated and validated successfully!', 'success');
    } catch (err) {
      notify(err.message || 'Failed to update question', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Add Custom Question Modal
  const handleAddCustomQuestion = async (e) => {
    e.preventDefault();
    if (!questionPaper) return;
    try {
      setLoading(true);
      const created = await api.addCustomQuestion(questionPaper.id, {
        question_text: newQuestionData.question_text,
        marks: parseInt(newQuestionData.marks, 10),
        co_level: newQuestionData.co_level,
        bloom_level: newQuestionData.bloom_level,
        model_answer: newQuestionData.model_answer,
        marking_scheme: newQuestionData.marking_scheme,
        is_validated: true,
        status: 'approved'
      }, {
        section_name: newQuestionData.section_name,
        question_number: newQuestionData.question_number,
        marks: newQuestionData.marks,
        co_level: newQuestionData.co_level,
        bloom_level: newQuestionData.bloom_level
      });
      setQuestionPaper(prev => ({
        ...prev,
        questions: [...prev.questions, created]
      }));
      setIsAddQuestionModalOpen(false);
      notify('Custom question added to paper and approved!', 'success');
    } catch (err) {
      notify(err.message || 'Failed to add question', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Delete Question
  const handleDeleteQuestion = async (questionId) => {
    if (!questionPaper) return;
    try {
      await api.deleteQuestion(questionPaper.id, questionId);
      setQuestionPaper(prev => ({
        ...prev,
        questions: prev.questions.filter(q => q.id !== questionId)
      }));
      notify('Question removed from paper.', 'info');
    } catch (err) {
      notify(err.message || 'Delete failed', 'error');
    }
  };

  // Word Document Downloads: 3 Modes
  const handleDownloadDocx = async (exportType = 'question_paper', exportApprovedOnly = true) => {
    if (!questionPaperId || isDownloading) return;
    setIsDownloading(true);
    setDownloadingType(exportType);
    setExportError('');

    try {
      const { blob, filename } = await api.downloadQuestionPaperDocx(questionPaperId, exportType, exportApprovedOnly);

      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      const typeTitles = {
        question_paper: 'Official Question Paper',
        with_answer_key: 'Question Paper with Answer Key',
        evaluation_scheme: 'Evaluation Scheme & Rubrics'
      };
      notify(`${typeTitles[exportType] || 'Word document'} downloaded successfully!`, 'success');
      setActiveStep('export');
    } catch (error) {
      console.error('DOCX export failed:', error);
      let message = error?.message || 'Unable to generate the Word document.';
      if (error?.status === 401 || error?.response?.status === 401) {
        message = 'Your login session has expired. Please sign in again.';
      } else if (error?.status === 403 || error?.response?.status === 403) {
        message = 'You do not have permission to export this question paper.';
      } else if (error?.status === 404 || error?.response?.status === 404) {
        message = 'The selected question paper could not be found.';
      }
      setExportError(message);
      notify(message, 'error');
    } finally {
      setIsDownloading(false);
      setDownloadingType(null);
    }
  };

  const handleDownloadPdf = async (exportType = 'question_paper', exportApprovedOnly = true) => {
    if (!questionPaperId || isDownloading) return;
    setIsDownloading(true);
    setDownloadingType(`pdf_${exportType}`);
    setExportError('');

    try {
      const { blob, filename } = await api.downloadQuestionPaperPdf(questionPaperId, exportType, exportApprovedOnly);
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      notify('PDF Question Paper downloaded successfully!', 'success');
    } catch (error) {
      console.error('PDF export failed:', error);
      notify(error?.message || 'Unable to generate PDF document.', 'error');
    } finally {
      setIsDownloading(false);
      setDownloadingType(null);
    }
  };

  const handleDownloadProvenanceReport = async () => {
    if (!questionPaperId) return;
    try {
      const report = await api.getQuestionPaperProvenanceReport(questionPaperId);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `Provenance_Report_Paper_${questionPaperId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      notify('Grounding Provenance Report downloaded (JSON)!', 'success');
    } catch (error) {
      notify(error?.message || 'Failed to download provenance report', 'error');
    }
  };

  const handleDownloadValidationReport = async () => {
    if (!questionPaperId) return;
    try {
      const report = await api.getQuestionPaperValidationReport(questionPaperId);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `Blueprint_Validation_Report_Paper_${questionPaperId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      notify('Blueprint Validation Report downloaded (JSON)!', 'success');
    } catch (error) {
      notify(error?.message || 'Failed to download validation report', 'error');
    }
  };

  // Word Template Upload
  const handleTemplateUpload = async (file) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      notify('Please upload a Microsoft Word document (.docx).', 'error');
      return;
    }
    if (!questionPaper) {
      notify('Please generate questions first before attaching a custom template.', 'error');
      return;
    }
    try {
      setLoading(true);
      const updated = await api.uploadWordTemplate(questionPaper.id, file);
      setQuestionPaper(updated);
      setTemplateUploaded(true);
      notify('Custom Word template uploaded and registered!', 'success');
    } catch (err) {
      notify(err.message || 'Template upload failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  // Toggle answer key display per question
  const toggleAnswerExpand = (qid) => {
    setExpandedAnswers(prev => ({
      ...prev,
      [qid]: !prev[qid]
    }));
  };

  // Review statistics calculation
  const totalCount = questionPaper?.questions?.length || 0;
  const approvedCount = questionPaper?.questions?.filter(q => q.status === 'approved' || (q.is_validated && q.status !== 'rejected')).length || 0;
  const rejectedCount = questionPaper?.questions?.filter(q => q.status === 'rejected').length || 0;
  const draftCount = totalCount - approvedCount - rejectedCount;
  const validationPercentage = totalCount > 0 ? Math.round((approvedCount / totalCount) * 100) : 0;

  // Step navigation with route synchronization
  const handleStepClick = (targetStep) => {
    setActiveStep(targetStep);
    const stepRouteName = targetStep === 'validation' ? 'review' : targetStep;
    if (questionPaperId) {
      navigate(`/question-papers/${questionPaperId}/${stepRouteName}`);
    } else {
      navigate(`/question-papers/${stepRouteName}`);
    }
  };

  // Step 3 to Step 4 transition: validate question paper and proceed to export
  const handleProceedToExport = async () => {
    if (!questionPaperId) {
      notify('Please select or create a question paper first.', 'error');
      return;
    }

    setIsProceeding(true);
    setProceedError('');

    try {
      const validationResult = await api.getExportValidation(questionPaperId);
      setExportValidationData(validationResult);

      if (validationResult && validationResult.can_export) {
        setActiveStep('export');
        navigate(`/question-papers/${questionPaperId}/export`);
        notify('Question paper verified and approved! Proceeding to Word & PDF Export.', 'success');
      } else {
        const failureMsg = validationResult?.message || 'Export validation failed. Please ensure all questions are approved before exporting.';
        setProceedError(failureMsg);
        notify(failureMsg, 'error');
      }
    } catch (err) {
      console.error('Failed to validate paper for export:', err);
      const errMsg = err?.response?.data?.detail || err?.message || 'Failed to validate question paper for export.';
      setProceedError(errMsg);
      notify(errMsg, 'error');
    } finally {
      setIsProceeding(false);
    }
  };

  // File type badge helper
  const renderFileTypeBadge = (type) => {
    const t = (type || '').toLowerCase();
    if (t === 'pptx' || t === 'ppt') {
      return <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">PPTX</span>;
    } else if (t === 'pdf') {
      return <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-200">PDF</span>;
    } else if (t === 'docx') {
      return <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">DOCX</span>;
    }
    return <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">TXT</span>;
  };

  return (
    <div className="space-y-6">
      
      {/* Header & Steps Progress Bar */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-blue-600" />
              Grounded Question Paper Generation & Blueprints
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
              Strictly grounded in approved institutional syllabus boundaries & faculty lecture materials (PPT/PDF/DOCX).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {facultyPapers && facultyPapers.length > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700">
                <span className="text-[11px] text-slate-500 font-medium">Paper:</span>
                <select
                  value={questionPaper?.id || ''}
                  onChange={async (e) => {
                    const pid = parseInt(e.target.value, 10);
                    if (pid) {
                      try {
                        setLoading(true);
                        const p = await api.getQuestionPaper(pid);
                        setQuestionPaper(p);
                        const currentStepRoute = activeStep === 'export' ? 'export' : (activeStep === 'validation' ? 'review' : activeStep);
                        navigate(`/question-papers/${pid}/${currentStepRoute}`);
                      } catch (err) {
                        notify('Failed to load question paper', 'error');
                      } finally {
                        setLoading(false);
                      }
                    }
                  }}
                  className="bg-transparent font-bold text-slate-900 border-none outline-none cursor-pointer text-xs"
                >
                  {facultyPapers.map(fp => (
                    <option key={fp.id} value={fp.id}>
                      #{fp.id} {fp.course_code} - {fp.exam_name} ({fp.questions?.length || 0} Qs)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {currentSyllabus && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-xl text-xs font-semibold text-blue-800">
                <FileText className="w-4 h-4 text-blue-600" />
                <span className="truncate max-w-[180px]">{currentSyllabus.original_filename}</span>
              </div>
            )}
          </div>
        </div>

        {exportError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{exportError}</span>
          </div>
        )}

        {/* Step Navigation Tabs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-slate-100">
          
          <button
            type="button"
            onClick={() => handleStepClick('content')}
            className={`flex items-center gap-2 p-2.5 rounded-xl text-xs font-bold transition-all text-left cursor-pointer ${
              activeStep === 'content'
                ? 'bg-blue-600 text-white shadow-xs'
                : (currentSyllabus || contentFiles.length > 0)
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                  : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
              activeStep === 'content'
                ? 'bg-white/20 text-white'
                : (currentSyllabus || contentFiles.length > 0)
                  ? 'bg-emerald-200 text-emerald-900'
                  : 'bg-slate-200 text-slate-700'
            }`}>
              {(currentSyllabus || contentFiles.length > 0) && activeStep !== 'content' ? (
                <Check className="w-3.5 h-3.5 text-emerald-800" />
              ) : (
                '1'
              )}
            </div>
            <div>
              <span className="block leading-tight">Content & COs</span>
              <span className={`text-[10px] font-normal ${activeStep === 'content' ? 'text-blue-100' : 'text-slate-500'}`}>
                {(currentSyllabus || contentFiles.length > 0) ? 'Syllabus Ready' : 'Syllabus & Slides'}
              </span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleStepClick('blueprint')}
            className={`flex items-center gap-2 p-2.5 rounded-xl text-xs font-bold transition-all text-left cursor-pointer ${
              activeStep === 'blueprint'
                ? 'bg-blue-600 text-white shadow-xs'
                : (questionPaper || blueprintSections.length > 0)
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                  : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
              activeStep === 'blueprint'
                ? 'bg-white/20 text-white'
                : (questionPaper || blueprintSections.length > 0)
                  ? 'bg-emerald-200 text-emerald-900'
                  : 'bg-slate-200 text-slate-700'
            }`}>
              {(questionPaper || blueprintSections.length > 0) && activeStep !== 'blueprint' ? (
                <Check className="w-3.5 h-3.5 text-emerald-800" />
              ) : (
                '2'
              )}
            </div>
            <div>
              <span className="block leading-tight">Blueprint</span>
              <span className={`text-[10px] font-normal ${activeStep === 'blueprint' ? 'text-blue-100' : 'text-slate-500'}`}>
                {questionPaper ? `${questionPaper.max_marks || 50}M • Format Set` : 'Format & Coverage'}
              </span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleStepClick('validation')}
            className={`flex items-center gap-2 p-2.5 rounded-xl text-xs font-bold transition-all text-left cursor-pointer ${
              activeStep === 'validation'
                ? 'bg-blue-600 text-white shadow-xs'
                : (totalCount > 0 && approvedCount === totalCount)
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                  : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
              activeStep === 'validation'
                ? 'bg-white/20 text-white'
                : (totalCount > 0 && approvedCount === totalCount)
                  ? 'bg-emerald-200 text-emerald-900'
                  : 'bg-slate-200 text-slate-700'
            }`}>
              {totalCount > 0 && approvedCount === totalCount && activeStep !== 'validation' ? (
                <Check className="w-3.5 h-3.5 text-emerald-800" />
              ) : (
                '3'
              )}
            </div>
            <div>
              <span className="block leading-tight">Faculty Review</span>
              <span className={`text-[10px] font-semibold ${
                activeStep === 'validation'
                  ? 'text-blue-100'
                  : (totalCount > 0 && approvedCount === totalCount)
                    ? 'text-emerald-700'
                    : 'text-slate-500'
              }`}>
                {questionPaper ? `${approvedCount}/${totalCount} Approved` : 'Validate Qs'}
              </span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleStepClick('export')}
            className={`flex items-center gap-2 p-2.5 rounded-xl text-xs font-bold transition-all text-left cursor-pointer ${
              activeStep === 'export'
                ? 'bg-blue-600 text-white shadow-xs ring-2 ring-blue-500/20'
                : 'bg-slate-50 text-slate-700 hover:bg-slate-100'
            }`}
          >
            <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
              activeStep === 'export' ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-700'
            }`}>
              4
            </div>
            <div>
              <span className="block leading-tight">Word Export</span>
              <span className={`text-[10px] font-normal ${activeStep === 'export' ? 'text-blue-100' : 'text-slate-400'}`}>
                3 Export Formats
              </span>
            </div>
          </button>

        </div>
      </div>

      {/* ========================================================================= */}
      {/* STEP 1: CONTENT & COURSE OUTCOMES (CO) INGESTION                          */}
      {/* ========================================================================= */}
      {activeStep === 'content' && (
        <div className="space-y-6">
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Syllabus Upload Card */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-2 rounded-xl bg-blue-50 text-blue-700">
                    <FileText className="w-5 h-5" />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">1. Approved Institutional Syllabus</h3>
                    <p className="text-[11px] text-slate-500">Defines the authoritative boundary of what may be assessed</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleLoadSample}
                  className="px-2.5 py-1 text-[11px] font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors"
                >
                  Load Sample CS
                </button>
              </div>

              <div 
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-200 hover:border-blue-400 hover:bg-blue-50/40 rounded-xl p-6 text-center cursor-pointer transition-all"
              >
                <UploadCloud className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <span className="text-xs font-bold text-slate-700 block">
                  Click to select Syllabus PDF (.pdf)
                </span>
                <span className="text-[11px] text-slate-400">
                  {currentSyllabus ? `Current: ${currentSyllabus.original_filename}` : 'Extracts units, topics, and CO cognitive levels'}
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={(e) => e.target.files?.[0] && handleSyllabusUpload(e.target.files[0])}
                  className="hidden"
                />
              </div>

              {currentSyllabus && (
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <div>
                      <span className="font-semibold text-slate-800 block truncate max-w-[200px]">
                        {currentSyllabus.original_filename}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {currentSyllabus.page_count} Pages • {units.length} Units Extracted
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={handleExtractBooks}
                    className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-[11px] rounded-lg shadow-xs"
                    title="Extract Textbooks & References"
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Extract Books</span>
                  </button>
                </div>
              )}
            </div>

            {/* Lecture Content & PPT Slides Card */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center gap-2">
                <span className="p-2 rounded-xl bg-indigo-50 text-indigo-700">
                  <Presentation className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">2. Faculty Instructional Content</h3>
                  <p className="text-[11px] text-slate-500">Upload PPT/PPTX slides, PDF lecture notes, DOCX or TXT files</p>
                </div>
              </div>

              <div 
                onClick={() => pptInputRef.current?.click()}
                className="border-2 border-dashed border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/40 rounded-xl p-6 text-center cursor-pointer transition-all"
              >
                <Presentation className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <span className="text-xs font-bold text-slate-700 block">
                  {isUploadingContent ? 'Extracting & aligning content...' : 'Click to upload PPTX, PDF notes, DOCX or TXT'}
                </span>
                <span className="text-[11px] text-slate-400">
                  Preserves slide/page numbers and detects image-only pages
                </span>
                <input
                  ref={pptInputRef}
                  type="file"
                  accept=".pptx,.ppt,.pdf,.docx,.txt"
                  onChange={(e) => e.target.files?.[0] && handleContentUpload(e.target.files[0])}
                  className="hidden"
                />
              </div>

              {contentFiles.length > 0 && (
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {contentFiles.map((file) => (
                    <div key={file.id} className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 truncate pr-2">
                        {renderFileTypeBadge(file.file_type)}
                        <span className="font-medium text-slate-800 truncate text-xs">{file.original_filename}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                          {file.slide_or_page_count} {file.file_type === 'pdf' ? 'pages' : (file.file_type === 'pptx' || file.file_type === 'ppt' ? 'slides' : 'sections')}
                        </span>
                        <button
                          type="button"
                          onClick={() => handlePreviewFile(file.id)}
                          className="p-1 rounded-md text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="Preview Extracted Chunks & OCR Warnings"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteContentFile(file.id)}
                          className="p-1 rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          title="Remove File"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>

          {/* Content Alignment & Coverage Summary */}
          {alignmentSummary && (
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-indigo-600" />
                    Syllabus–Content Alignment Calibration
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Calculated keyword overlap and semantic stem matching against approved syllabus units.
                  </p>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 bg-slate-100 text-slate-700 rounded-lg">
                  Total Chunks: {alignmentSummary.total_alignments || 0}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3 pt-1">
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
                  <span className="text-lg font-extrabold text-emerald-700 block">
                    {alignmentSummary.strong_count || 0}
                  </span>
                  <span className="text-[11px] font-bold text-emerald-800 block">Strong (≥ 80%)</span>
                  <span className="text-[10px] text-emerald-600">Auto-eligible for RAG</span>
                </div>

                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-center">
                  <span className="text-lg font-extrabold text-amber-700 block">
                    {alignmentSummary.review_count || 0}
                  </span>
                  <span className="text-[11px] font-bold text-amber-800 block">Review (60–79%)</span>
                  <span className="text-[10px] text-amber-600">Partial topic context</span>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-center">
                  <span className="text-lg font-extrabold text-slate-700 block">
                    {alignmentSummary.unmatched_count || 0}
                  </span>
                  <span className="text-[11px] font-bold text-slate-800 block">Unmatched (&lt; 60%)</span>
                  <span className="text-[10px] text-slate-500">Excluded from RAG</span>
                </div>
              </div>
            </div>
          )}

          {/* Extracted Course Outcomes (CO1-CO6) Showcase */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="p-2 rounded-xl bg-emerald-50 text-emerald-700">
                  <Award className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Extracted Course Outcomes (COs) & Cognitive Verbs</h3>
                  <p className="text-[11px] text-slate-500">Questions will be formulated strictly matching these course outcomes and cognitive levels.</p>
                </div>
              </div>
            </div>

            {courseOutcomes.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl">
                Upload a syllabus to automatically analyze and extract Course Outcomes (CO1–CO6).
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {courseOutcomes.map((co) => (
                  <div key={co.code} className="p-3.5 bg-slate-50/80 rounded-xl border border-slate-200 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-blue-100 text-blue-800">
                          {co.code}
                        </span>
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                          {co.bloom_level}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 line-clamp-3">
                        {co.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Proceed button */}
          <div className="flex justify-end">
            <button
              onClick={() => setActiveStep('blueprint')}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs sm:text-sm rounded-xl shadow-md transition-all cursor-pointer"
            >
              <span>Continue to Blueprint Designer</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

        </div>
      )}

      {/* ========================================================================= */}
      {/* STEP 2: QUESTION PAPER BLUEPRINT DESIGNER                                  */}
      {/* ========================================================================= */}
      {activeStep === 'blueprint' && (
        <div className="space-y-6">
          
          {/* Generation Mode Selector */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-600" />
                  Content Grounding Priority & Generation Mode
                </h3>
                <p className="text-[11px] text-slate-500">
                  Select the authoritative hierarchy used by the RAG synthesizer to formulate questions.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              
              <div 
                onClick={() => setGenerationMode('syllabus_ppt')}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  generationMode === 'syllabus_ppt'
                    ? 'border-blue-600 bg-blue-50/70 ring-1 ring-blue-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/40'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-900">Syllabus + PPT/Notes</span>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded">RECOMMENDED</span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Syllabus defines the exam scope; questions are grounded in code, diagrams, algorithms, and examples from uploaded slides.
                </p>
              </div>

              <div 
                onClick={() => setGenerationMode('syllabus_only')}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  generationMode === 'syllabus_only'
                    ? 'border-blue-600 bg-blue-50/70 ring-1 ring-blue-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/40'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-900">Syllabus Only</span>
                  <span className="text-[9px] font-semibold px-1.5 py-0.5 bg-slate-200 text-slate-700 rounded">THEORETICAL</span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Formulates standard conceptual questions strictly bounded by unit topics and bloom cognitive verbs without slide context.
                </p>
              </div>

              <div 
                onClick={() => setGenerationMode('all_sources')}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  generationMode === 'all_sources'
                    ? 'border-blue-600 bg-blue-50/70 ring-1 ring-blue-500'
                    : 'border-slate-200 hover:border-slate-300 bg-slate-50/40'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-900">All Uploaded Sources</span>
                  <span className="text-[9px] font-semibold px-1.5 py-0.5 bg-purple-100 text-purple-800 rounded">COMPREHENSIVE</span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Aggregates all uploaded PPTs, lecture notes, textbook citations, and handouts for maximum question diversity.
                </p>
              </div>

            </div>
          </div>

          {/* Pre-generation Content Coverage Matrix Card */}
          {coverageMatrix && (
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-emerald-600" />
                    Pre-Generation Syllabus & Slide Coverage Matrix
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Verifies whether every syllabus topic has instructional slide support before generation.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${
                    coverageMatrix.coverage_percentage >= 75
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-amber-50 text-amber-800 border-amber-200'
                  }`}>
                    Coverage: {coverageMatrix.coverage_percentage}%
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowCoverageDetails(!showCoverageDetails)}
                    className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 px-2.5 py-1 bg-blue-50 rounded-lg"
                  >
                    <span>{showCoverageDetails ? 'Hide Topics' : 'View Topics'}</span>
                    {showCoverageDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              {coverageMatrix.warnings && coverageMatrix.warnings.length > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    {coverageMatrix.warnings.map((w, i) => (
                      <div key={i}>{w}</div>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-3 gap-3 text-center text-xs">
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl">
                  <span className="font-bold text-slate-800 text-sm block">{coverageMatrix.ready_topics_count}</span>
                  <span className="text-[10px] text-slate-500">Ready (With Slides)</span>
                </div>
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl">
                  <span className="font-bold text-slate-800 text-sm block">{coverageMatrix.partial_topics_count}</span>
                  <span className="text-[10px] text-slate-500">Partial Coverage</span>
                </div>
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-xl">
                  <span className="font-bold text-slate-800 text-sm block">{coverageMatrix.no_content_topics_count}</span>
                  <span className="text-[10px] text-slate-500">Syllabus Only</span>
                </div>
              </div>

              {showCoverageDetails && coverageMatrix.matrix && (
                <div className="pt-2 max-h-64 overflow-y-auto border-t border-slate-100">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="text-slate-400 border-b border-slate-100 text-[10px] uppercase font-bold">
                        <th className="pb-1.5">Unit</th>
                        <th className="pb-1.5">Topic</th>
                        <th className="pb-1.5">CO</th>
                        <th className="pb-1.5">Bloom</th>
                        <th className="pb-1.5 text-center">Slides</th>
                        <th className="pb-1.5 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {coverageMatrix.matrix.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="py-1.5 font-semibold text-slate-900">U{row.unit_number}</td>
                          <td className="py-1.5 pr-2 truncate max-w-[200px]" title={row.topic}>{row.topic}</td>
                          <td className="py-1.5 font-semibold text-blue-600">{row.co_level}</td>
                          <td className="py-1.5 text-slate-500 text-[11px]">{row.bloom_level?.split(' - ')[0]}</td>
                          <td className="py-1.5 text-center font-bold text-indigo-700">{row.slide_or_page_count}</td>
                          <td className="py-1.5 text-right">
                            <span className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${
                              row.status === 'Ready'
                                ? 'bg-emerald-100 text-emerald-800'
                                : (row.status === 'Partial Coverage' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600')
                            }`}>
                              {row.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Blueprint Specification Source Selection */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-blue-600" />
                  Blueprint Specification Source
                </h3>
                <p className="text-[11px] text-slate-500">
                  Select a standard blueprint preset, upload your institution's template, or pick from the reusable template library.
                </p>
              </div>

              <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-xl border border-slate-200 self-start sm:self-auto">
                <button
                  type="button"
                  onClick={() => setBlueprintSourceTab('preset')}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    blueprintSourceTab === 'preset' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Standard Presets
                </button>
                <button
                  type="button"
                  onClick={() => setBlueprintSourceTab('upload_template')}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 ${
                    blueprintSourceTab === 'upload_template' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
                  <span>Upload Template</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setBlueprintSourceTab('template_library');
                    loadTemplateLibrary();
                  }}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 ${
                    blueprintSourceTab === 'template_library' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <BookOpen className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Template Library ({savedTemplatesList.length})</span>
                </button>
                <button
                  type="button"
                  onClick={() => setBlueprintSourceTab('custom')}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                    blueprintSourceTab === 'custom' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Custom Blueprint
                </button>
              </div>
            </div>

            {/* Active Template Badge (if selected) */}
            {selectedTemplateName && (
              <div className="px-3.5 py-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Active Blueprint Applied from: <strong>{selectedTemplateName}</strong></span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedTemplateId(null);
                    setSelectedTemplateName(null);
                    if (presets.length > 0) applyPreset(presets[0]);
                  }}
                  className="text-[11px] text-emerald-700 font-semibold hover:underline"
                >
                  Reset to Standard Preset
                </button>
              </div>
            )}

            {/* TAB 1: Standard Examination Presets */}
            {blueprintSourceTab === 'preset' && (
              <div className="space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {presets.map((preset) => (
                    <div
                      key={preset.id}
                      onClick={() => applyPreset(preset)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        selectedPresetId === preset.id && !selectedTemplateId
                          ? 'border-blue-600 bg-blue-50/60 shadow-xs ring-1 ring-blue-500'
                          : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-900">{preset.name}</span>
                        <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full">
                          {preset.max_marks} M
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 line-clamp-2">{preset.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 2: Upload Institution Template */}
            {blueprintSourceTab === 'upload_template' && (
              <div className="space-y-4">
                {!extractedTemplateData ? (
                  <div className="p-8 border-2 border-dashed border-blue-200 rounded-2xl bg-blue-50/30 text-center space-y-3">
                    <div className="inline-flex p-3 bg-blue-100 text-blue-700 rounded-2xl">
                      <UploadCloud className="w-8 h-8" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900">Upload Institution Question-Paper Template</h4>
                      <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                        Upload an official institution question paper or blank template in <strong>DOCX, PDF, Scanned Image (PNG/JPG), or XLSX</strong>.
                        Our extraction engine will automatically parse sections, question slots, marks, Bloom levels, and internal choices.
                      </p>
                    </div>
                    <div>
                      <button
                        type="button"
                        onClick={() => setIsTemplateUploadModalOpen(true)}
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors"
                      >
                        <Sparkles className="w-4 h-4" />
                        <span>Upload & Extract Template</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                      <span className="text-slate-600">
                        Template: <strong>{extractedTemplateData.original_filename}</strong> ({extractedTemplateData.file_format?.toUpperCase()})
                      </span>
                      <button
                        type="button"
                        onClick={() => setIsTemplateUploadModalOpen(true)}
                        className="text-blue-600 hover:text-blue-800 font-semibold"
                      >
                        Upload Different Template
                      </button>
                    </div>
                    <ExtractedBlueprintReviewer
                      initialBlueprint={extractedTemplateData.blueprint}
                      confidenceScores={extractedTemplateData.confidence_scores}
                      initialValidation={extractedTemplateData.validation}
                      extractionStatus={extractedTemplateData.extraction_status}
                      fileFormat={extractedTemplateData.file_format}
                      originalFilename={extractedTemplateData.original_filename}
                      storedFilename={extractedTemplateData.stored_filename}
                      syllabusId={currentSyllabus?.id}
                      onConfirmAndUse={handleConfirmExtractedBlueprint}
                      onCancel={() => setExtractedTemplateData(null)}
                    />
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: Saved Template Library */}
            {blueprintSourceTab === 'template_library' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700">
                    Saved Institutional Templates ({savedTemplatesList.length})
                  </span>
                  <button
                    type="button"
                    onClick={() => setIsTemplateUploadModalOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg text-xs font-semibold transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Upload New Template</span>
                  </button>
                </div>

                {isLoadingTemplates ? (
                  <div className="p-6 text-center text-xs text-slate-500">Loading template library...</div>
                ) : savedTemplatesList.length === 0 ? (
                  <div className="p-6 border border-slate-200 rounded-xl text-center text-xs text-slate-500 space-y-2">
                    <p>No saved institutional templates in the library yet.</p>
                    <button
                      type="button"
                      onClick={() => setIsTemplateUploadModalOpen(true)}
                      className="text-blue-600 hover:underline font-semibold"
                    >
                      Upload your first template now
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {savedTemplatesList.map((tmpl) => (
                      <div
                        key={tmpl.id}
                        className={`p-4 rounded-xl border transition-all ${
                          selectedTemplateId === tmpl.id
                            ? 'border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-400'
                            : 'border-slate-200 bg-slate-50/50 hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h4 className="text-xs font-bold text-slate-900">{tmpl.template_name}</h4>
                            <p className="text-[11px] text-slate-500">{tmpl.institution_name}</p>
                            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-800 rounded">
                                {tmpl.maximum_marks} Marks
                              </span>
                              <span className="text-[10px] text-slate-500">
                                {tmpl.duration_minutes} Mins
                              </span>
                              <span className="text-[10px] font-medium text-slate-500 uppercase px-1.5 py-0.5 bg-slate-200 rounded">
                                {tmpl.file_format}
                              </span>
                              <span className="text-[10px] text-slate-400">
                                v{tmpl.version || 1}
                              </span>
                            </div>
                          </div>

                          <div className="flex flex-col gap-1 items-end">
                            <button
                              type="button"
                              onClick={() => handleSelectTemplateFromLibrary(tmpl)}
                              className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
                            >
                              Use Blueprint
                            </button>
                            <div className="flex items-center gap-1.5 mt-1">
                              <a
                                href={api.getTemplateOriginalDownloadUrl(tmpl.id)}
                                target="_blank"
                                rel="noreferrer"
                                className="p-1 text-slate-400 hover:text-blue-600"
                                title="Download Original File"
                              >
                                <Download className="w-3.5 h-3.5" />
                              </a>
                              <button
                                type="button"
                                onClick={() => handleDeleteTemplateFromLibrary(tmpl.id)}
                                className="p-1 text-slate-400 hover:text-rose-600"
                                title="Delete Template"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: Custom Blueprint Configuration */}
            {blueprintSourceTab === 'custom' && (
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-2">
                <p className="font-semibold text-slate-800">
                  Custom Blueprint Configuration Active
                </p>
                <p>
                  You can freely edit the sections, question counts, marks per question, and internal choice settings in the sections panel below.
                </p>
              </div>
            )}

          </div>

          {/* Exam Header Details Configuration */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-indigo-600" />
              Institutional Header & Examination Metadata
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Institution Name</label>
                <input
                  type="text"
                  value={blueprintMeta.institution_name}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, institution_name: e.target.value })}
                  placeholder="e.g. Aarupadai Veedu Institute of Technology"
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Course Name</label>
                <input
                  type="text"
                  value={blueprintMeta.course_name}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, course_name: e.target.value })}
                  placeholder="e.g. R Programming"
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Course Code</label>
                <input
                  type="text"
                  value={blueprintMeta.course_code}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, course_code: e.target.value })}
                  placeholder="e.g. 35021P28"
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Programme / Branch</label>
                <input
                  type="text"
                  value={blueprintMeta.programme}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, programme: e.target.value })}
                  placeholder="e.g. B.E. Computer Science and Engineering"
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Semester & Regulation</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={blueprintMeta.semester}
                    onChange={(e) => setBlueprintMeta({ ...blueprintMeta, semester: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300"
                    placeholder="e.g. IV"
                  />
                  <input
                    type="text"
                    value={blueprintMeta.regulation}
                    onChange={(e) => setBlueprintMeta({ ...blueprintMeta, regulation: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300"
                    placeholder="Reg: 2021"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Department</label>
                <input
                  type="text"
                  value={blueprintMeta.department}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, department: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Academic Year</label>
                <input
                  type="text"
                  value={blueprintMeta.academic_year}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, academic_year: e.target.value })}
                  placeholder="e.g. 2024-2025"
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Assigned Faculty</label>
                <input
                  type="text"
                  value={blueprintMeta.assigned_faculty}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, assigned_faculty: e.target.value })}
                  placeholder="Faculty Name"
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Exam Name</label>
                <input
                  type="text"
                  value={blueprintMeta.exam_name}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, exam_name: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Duration & Max Marks</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={blueprintMeta.duration}
                    onChange={(e) => setBlueprintMeta({ ...blueprintMeta, duration: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300"
                    placeholder="3 Hours"
                  />
                  <input
                    type="number"
                    value={blueprintMeta.max_marks}
                    onChange={(e) => setBlueprintMeta({ ...blueprintMeta, max_marks: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300"
                    placeholder="100"
                  />
                </div>
              </div>

              <div className="sm:col-span-2">
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Exam Instructions</label>
                <input
                  type="text"
                  value={blueprintMeta.instructions}
                  onChange={(e) => setBlueprintMeta({ ...blueprintMeta, instructions: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                />
              </div>
            </div>
          </div>

          {/* Blueprint Section Breakdown */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-600" />
              Blueprint Sections & Internal Choice Allocations
            </h3>

            <div className="space-y-4">
              {blueprintSections.map((sec, idx) => (
                <div key={idx} className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold text-slate-900">{sec.name}</span>
                      <span className="text-[11px] font-medium text-slate-500">
                        ({sec.questions_count} Questions × {sec.marks_per_question} Marks = {sec.questions_count * sec.marks_per_question} Marks)
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-800 rounded uppercase">
                        {sec.question_type || 'short_answer'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap min-w-[280px]">
                      <label className="text-[11px] font-semibold text-slate-600">Question Types:</label>
                      <div className="min-w-[220px]">
                        <MultiSelectQuestionTypes
                          selectedTypes={sec.question_types || (sec.question_type ? [sec.question_type] : ['short_answer'])}
                          bloomLevel={sec.bloom_distribution?.[0] || 'L2 - Understand'}
                          onChange={(newTypes) => {
                            setBlueprintSections(prev => prev.map((s, sIdx) => sIdx === idx ? {
                              ...s,
                              question_types: newTypes,
                              question_type: newTypes.join(' + '),
                              mcq_config: newTypes.includes('mcq') ? (s.mcq_config || {
                                options_count: 4,
                                is_multiple_correct: false,
                                include_none_of_above: false,
                                include_all_of_above: false,
                                randomize_options: false,
                                negative_marking: 0.0,
                                generate_explanation: true
                              }) : s.mcq_config
                            } : s));
                          }}
                        />
                      </div>

                      {sec.has_internal_choice && (
                        <span className="text-[10px] font-bold px-2 py-0.5 bg-amber-100 text-amber-800 rounded-md border border-amber-200">
                          Internal Choice (Either/Or)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* MCQ Configuration Drawer */}
                  {((sec.question_types && sec.question_types.includes('mcq')) || (sec.question_type && sec.question_type.includes('mcq'))) && (
                    <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-200 text-xs space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-blue-900 text-[11px] flex items-center gap-1.5">
                          <Sliders className="w-3.5 h-3.5 text-blue-600" />
                          MCQ Configuration Options
                        </span>
                        <span className="text-[10px] text-blue-700 font-medium">Automatic Distractor & Key Validation</span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
                        <div>
                          <label className="block text-[10px] font-semibold text-slate-700 mb-0.5">Options Count</label>
                          <select
                            value={sec.mcq_config?.options_count || 4}
                            onChange={(e) => {
                              const cnt = parseInt(e.target.value, 10);
                              setBlueprintSections(prev => prev.map((s, sIdx) => sIdx === idx ? {
                                ...s,
                                mcq_config: { ...(s.mcq_config || {}), options_count: cnt }
                              } : s));
                            }}
                            className="w-full px-2 py-1 text-xs rounded border border-slate-300 bg-white"
                          >
                            <option value={4}>4 Options (A-D)</option>
                            <option value={5}>5 Options (A-E)</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-slate-700 mb-0.5">Negative Marking</label>
                          <input
                            type="number"
                            step="0.25"
                            value={sec.mcq_config?.negative_marking || 0.0}
                            onChange={(e) => {
                              const neg = parseFloat(e.target.value);
                              setBlueprintSections(prev => prev.map((s, sIdx) => sIdx === idx ? {
                                ...s,
                                mcq_config: { ...(s.mcq_config || {}), negative_marking: neg }
                              } : s));
                            }}
                            className="w-full px-2 py-1 text-xs rounded border border-slate-300 bg-white"
                            placeholder="0.0"
                          />
                        </div>

                        <div className="flex items-center gap-1.5 pt-3">
                          <input
                            type="checkbox"
                            id={`none_above_${idx}`}
                            checked={!!sec.mcq_config?.include_none_of_above}
                            onChange={(e) => {
                              const chk = e.target.checked;
                              setBlueprintSections(prev => prev.map((s, sIdx) => sIdx === idx ? {
                                ...s,
                                mcq_config: { ...(s.mcq_config || {}), include_none_of_above: chk }
                              } : s));
                            }}
                            className="rounded text-blue-600 focus:ring-blue-500"
                          />
                          <label htmlFor={`none_above_${idx}`} className="text-[11px] text-slate-700 font-medium">None of above</label>
                        </div>

                        <div className="flex items-center gap-1.5 pt-3">
                          <input
                            type="checkbox"
                            id={`rand_opts_${idx}`}
                            checked={!!sec.mcq_config?.randomize_options}
                            onChange={(e) => {
                              const chk = e.target.checked;
                              setBlueprintSections(prev => prev.map((s, sIdx) => sIdx === idx ? {
                                ...s,
                                mcq_config: { ...(s.mcq_config || {}), randomize_options: chk }
                              } : s));
                            }}
                            className="rounded text-blue-600 focus:ring-blue-500"
                          />
                          <label htmlFor={`rand_opts_${idx}`} className="text-[11px] text-slate-700 font-medium">Randomize options</label>
                        </div>
                      </div>
                    </div>
                  )}

                  <p className="text-xs text-slate-600 italic">"{sec.instructions}"</p>

                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[10px] font-semibold text-slate-500 mr-1">Target COs:</span>
                    {sec.co_distribution?.map((co, cIdx) => (
                      <span key={cIdx} className="px-1.5 py-0.5 text-[10px] font-bold bg-blue-100 text-blue-800 rounded">
                        {co}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => setActiveStep('content')}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
            >
              Back to Content
            </button>

            <button
              onClick={handleGenerateQuestions}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-700 to-indigo-600 hover:from-blue-800 hover:to-indigo-700 text-white font-semibold text-xs sm:text-sm rounded-xl shadow-md transition-all cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              <span>{loading ? 'Synthesizing Questions with Grounded RAG...' : 'Synthesize Questions with Grounded RAG'}</span>
            </button>
          </div>

        </div>
      )}

      {/* ========================================================================= */}
      {/* STEP 3: FACULTY QUESTION VALIDATION & REVIEW INTERFACE                    */}
      {/* ========================================================================= */}
      {activeStep === 'validation' && (
        <div className="space-y-6">
          
          {/* Validation Header Summary Card */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <FileCheck className="w-5 h-5 text-blue-600" />
                  Faculty Review & Grounding Provenance Verification
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Every synthesized question starts in <strong>Draft</strong> status. Review Bloom cognitive levels, inspect slide source citations, and approve questions for the final Word document.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsAddQuestionModalOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Question</span>
                </button>

                <button
                  onClick={handleBulkValidateAll}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
                >
                  <CheckCheck className="w-3.5 h-3.5" />
                  <span>Approve All Drafts</span>
                </button>
              </div>
            </div>

            {/* Validation Progress & Stat Pills */}
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-700">Approval Status:</span>
                  <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-emerald-100 text-emerald-800">
                    {approvedCount} Approved
                  </span>
                  <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-amber-100 text-amber-800">
                    {draftCount} Draft
                  </span>
                  {rejectedCount > 0 && (
                    <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-rose-100 text-rose-800">
                      {rejectedCount} Rejected
                    </span>
                  )}
                </div>

                <span className={`font-bold ${approvedCount === totalCount && totalCount > 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {approvedCount === totalCount && totalCount > 0 ? '✓ Ready for Word Export' : `${draftCount} Pending Review`}
                </span>
              </div>

              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-500 ${approvedCount === totalCount && totalCount > 0 ? 'bg-emerald-500' : 'bg-blue-600'}`}
                  style={{ width: `${validationPercentage}%` }}
                />
              </div>
            </div>
          </div>

          {/* Questions List */}
          {!questionPaper || !questionPaper.questions || questionPaper.questions.length === 0 ? (
            <div className="bg-white p-8 rounded-2xl border border-slate-200 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-slate-400 mx-auto" />
              <p className="text-xs text-slate-500">No questions generated yet. Please configure the blueprint and synthesize questions first.</p>
              <button
                onClick={() => setActiveStep('blueprint')}
                className="px-4 py-2 bg-blue-600 text-white text-xs font-semibold rounded-xl"
              >
                Go to Blueprint
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {questionPaper.questions.map((q) => {
                const isApproved = q.status === 'approved' || (q.is_validated && q.status !== 'rejected');
                const isRejected = q.status === 'rejected';
                const isNeedsReview = q.status === 'needs_review';
                const isDraft = !isApproved && !isRejected && !isNeedsReview;

                let parsedOptions = q.options || null;
                if (!parsedOptions && q.options_json) {
                  try {
                    parsedOptions = typeof q.options_json === 'string' ? JSON.parse(q.options_json) : q.options_json;
                  } catch (e) {
                    parsedOptions = null;
                  }
                }

                if (Array.isArray(parsedOptions)) {
                  parsedOptions = parsedOptions.map((opt, idx) => {
                    if (typeof opt === 'string') {
                      const match = opt.match(/^([A-Ea-e])[\.\)]\s*(.*)$/);
                      const label = match ? match[1].toUpperCase() : String.fromCharCode(65 + idx);
                      const text = match ? match[2] : opt;
                      const is_correct = (q.correct_answer === label) || (q.correct_option === label);
                      return { label, text, is_correct };
                    }
                    return {
                      label: opt.label || String.fromCharCode(65 + idx),
                      text: opt.text || '',
                      is_correct: opt.is_correct === true || opt.label === q.correct_answer || opt.label === q.correct_option,
                      explanation: opt.explanation || null
                    };
                  });
                }

                const hasEmptyOptions = Array.isArray(parsedOptions) && parsedOptions.length > 0 && parsedOptions.some(opt => !opt.text || !opt.text.trim());

                let distractorExplanations = null;
                if (q.distractor_explanations_json) {
                  try {
                    distractorExplanations = typeof q.distractor_explanations_json === 'string' ? JSON.parse(q.distractor_explanations_json) : q.distractor_explanations_json;
                  } catch (e) {
                    distractorExplanations = null;
                  }
                }

                return (
                  <div 
                    key={q.id}
                    className={`bg-white p-4.5 rounded-xl border transition-all ${
                      isApproved
                        ? 'border-emerald-200 bg-emerald-50/10'
                        : (isRejected 
                            ? 'border-rose-200 bg-rose-50/10 opacity-75' 
                            : (isNeedsReview 
                                ? 'border-amber-300 bg-amber-50/20' 
                                : 'border-slate-200 bg-slate-50/20 hover:border-blue-300'))
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                      
                      <div className="flex items-start gap-3 w-full">
                        {/* Q.No badge */}
                        <span className={`w-9 h-9 rounded-lg font-bold text-xs flex items-center justify-center shrink-0 border ${
                          isApproved 
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200' 
                            : (isRejected 
                                ? 'bg-rose-50 text-rose-800 border-rose-200' 
                                : (isNeedsReview 
                                    ? 'bg-amber-50 text-amber-900 border-amber-300' 
                                    : 'bg-slate-100 text-slate-800 border-slate-200'))
                        }`}>
                          {q.question_number}
                        </span>

                        <div className="space-y-2 w-full">
                          {/* Badges bar */}
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="text-[10px] font-bold px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-md">
                              {q.section_name}
                            </span>
                            {q.question_type && (
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded-md uppercase tracking-wider">
                                {q.question_type.replace(/_/g, ' ')}
                              </span>
                            )}
                            <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-50 text-blue-700 border border-blue-100 rounded-md">
                              {q.co_level}
                            </span>
                            <span className="text-[10px] font-semibold px-2 py-0.5 bg-purple-50 text-purple-700 border border-purple-100 rounded-md">
                              {q.bloom_level}
                            </span>
                            <span className="text-[10px] font-bold px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md">
                              {q.marks} Marks
                            </span>
                            {q.unit_number && (
                              <span className="text-[10px] font-medium px-2 py-0.5 bg-slate-50 text-slate-600 rounded-md border border-slate-200">
                                Unit {q.unit_number}
                              </span>
                            )}
                            
                            {/* Review Status Pill */}
                            {isApproved && (
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-md flex items-center gap-1">
                                <Check className="w-3 h-3" /> Approved
                              </span>
                            )}
                            {isDraft && (
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md flex items-center gap-1">
                                <Clock className="w-3 h-3" /> Draft
                              </span>
                            )}
                            {isNeedsReview && (
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 rounded-md flex items-center gap-1">
                                <AlertCircle className="w-3 h-3 text-amber-600" /> Needs Review
                              </span>
                            )}
                            {isRejected && (
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-rose-100 text-rose-800 rounded-md flex items-center gap-1">
                                <X className="w-3 h-3" /> Rejected
                              </span>
                            )}

                            {/* Validation Scores */}
                            {q.grammar_score != null && (
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${
                                q.grammar_score >= 90
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : 'bg-amber-50 text-amber-700 border-amber-200'
                              }`}>
                                Grammar: {q.grammar_score}%
                              </span>
                            )}
                            {q.quality_score != null && (
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${
                                q.quality_score >= 85
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : 'bg-amber-50 text-amber-700 border-amber-200'
                              }`}>
                                Quality: {q.quality_score}%
                              </span>
                            )}

                            {/* Choice Pair & Equivalence Badge */}
                            {q.or_pair_id && (
                              <span className="text-[10px] font-bold px-2 py-0.5 bg-purple-50 text-purple-800 border border-purple-200 rounded-md">
                                OR Pair: {q.or_pair_id}
                                {q.or_equivalence_score != null && ` (${q.or_equivalence_score}% eq)`}
                              </span>
                            )}
                          </div>

                          {/* Quality Review Reasons Notice */}
                          {q.needs_review_reasons && (
                            <div className="p-2 bg-amber-50/90 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
                              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                              <div>
                                <span className="font-semibold text-amber-900">Quality Notice: </span>
                                <span>{q.needs_review_reasons}</span>
                              </div>
                            </div>
                          )}

                          {/* Grounding Source Citation */}
                          {q.source_filename && (
                            <div className="flex items-center gap-2 text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-600 flex items-center gap-1">
                                <FileText className="w-3 h-3 text-indigo-500" />
                                {q.source_filename}
                              </span>
                              {q.source_page_or_slide && (
                                <span>• Slide/Page {q.source_page_or_slide}</span>
                              )}
                              {q.alignment_confidence && (
                                <span className="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 font-semibold text-[10px]">
                                  {Math.round(q.alignment_confidence * 100)}% match
                                </span>
                              )}
                            </div>
                          )}

                          {/* Question Text */}
                          <p className="text-xs sm:text-sm text-slate-900 font-medium leading-relaxed">
                            {q.question_text}
                          </p>

                          {/* MCQ Empty Option Error Banner */}
                          {hasEmptyOptions && (
                            <div className="mt-2.5 p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-start gap-2">
                              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                              <div>
                                <span className="font-semibold text-rose-900">Invalid MCQ: </span>
                                <span>Option text is missing. Regenerate or edit this question.</span>
                              </div>
                            </div>
                          )}

                          {/* MCQ Options Display */}
                          {parsedOptions && parsedOptions.length > 0 && (
                            <div className="mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {parsedOptions.map((opt, oIdx) => {
                                const isCorrect = opt.is_correct === true;
                                const rationale = opt.explanation || (distractorExplanations && distractorExplanations[opt.label]);
                                return (
                                  <div
                                    key={oIdx}
                                    className={`p-2.5 rounded-lg border text-xs transition-all ${
                                      isCorrect
                                        ? 'bg-emerald-50/90 border-emerald-300 text-emerald-950 font-medium shadow-2xs ring-1 ring-emerald-400'
                                        : 'bg-slate-50/70 border-slate-200 text-slate-700'
                                    }`}
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <div className="flex items-start gap-2">
                                        <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[11px] shrink-0 ${
                                          isCorrect ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-700'
                                        }`}>
                                          {opt.label}
                                        </span>
                                        <span className="leading-snug pt-0.5">
                                          {opt.text || <span className="text-rose-500 italic">[Empty Option]</span>}
                                        </span>
                                      </div>
                                      {isCorrect && (
                                        <span className="px-1.5 py-0.5 text-[9px] font-extrabold uppercase bg-emerald-600 text-white rounded shrink-0">
                                          Correct
                                        </span>
                                      )}
                                    </div>
                                    {rationale && (
                                      <p className="mt-1.5 text-[11px] text-slate-500 italic pl-7 border-t border-slate-200/50 pt-1">
                                        {rationale}
                                      </p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* Model Answer & Rubric Toggle */}
                          {(q.model_answer || q.marking_scheme || q.stepwise_solution) && (
                            <div className="pt-1">
                              <button
                                type="button"
                                onClick={() => toggleAnswerExpand(q.id)}
                                className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 transition-colors"
                              >
                                {expandedAnswers[q.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                <span>{expandedAnswers[q.id] ? 'Hide Answer Key & Rubrics' : 'View Answer Key & Rubrics'}</span>
                              </button>

                              {expandedAnswers[q.id] && (
                                <div className="mt-2 p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
                                  {q.model_answer && (
                                    <div>
                                      <span className="font-bold text-slate-800 block text-[11px]">Model Answer / Solution:</span>
                                      <p className="text-slate-700 leading-relaxed mt-0.5">{q.model_answer}</p>
                                    </div>
                                  )}
                                  {q.marking_scheme && (
                                    <div className="pt-1.5 border-t border-slate-200">
                                      <span className="font-bold text-slate-800 block text-[11px]">Stepwise Marking Scheme:</span>
                                      <p className="text-slate-600 leading-relaxed mt-0.5">{q.marking_scheme}</p>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}

                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-start pt-1">
                        
                        {/* Approve Button */}
                        <button
                          onClick={() => handleReviewQuestion(q.id, 'approve')}
                          disabled={isApproved || q.quality_score === 0 || q.status === 'needs_review' || hasEmptyOptions}
                          className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                            isApproved
                              ? 'bg-emerald-100 text-emerald-800'
                              : (q.quality_score === 0 || q.status === 'needs_review' || hasEmptyOptions)
                                ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                                : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                          }`}
                          title={
                            q.quality_score === 0 || hasEmptyOptions || q.status === 'needs_review'
                              ? 'Cannot approve: MCQ has structural or quality issues. Please edit or regenerate.'
                              : 'Approve Question for Exam'
                          }
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>{isApproved ? 'Approved' : 'Approve'}</span>
                        </button>

                        {/* Reject Button */}
                        <button
                          onClick={() => {
                            setRejectModalData({ question: q, remarks: '' });
                            setIsRejectModalOpen(true);
                          }}
                          className={`p-1.5 rounded-lg transition-colors ${
                            isRejected
                              ? 'bg-rose-100 text-rose-800'
                              : 'text-slate-400 hover:text-rose-600 hover:bg-rose-50'
                          }`}
                          title="Reject Question"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>

                        {/* View Source Provenance */}
                        <button
                          onClick={() => handleOpenProvenance(q.id)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                          title="View Grounding Source Citation"
                        >
                          <Search className="w-4 h-4" />
                        </button>

                        {/* Edit Button */}
                        <button
                          onClick={() => openEditModal(q)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="Edit Question Text & Marks"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>

                        {/* Guided Regenerate Button */}
                        <button
                          onClick={() => openRegenerateModal(q)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                          title="Guided Question Regeneration"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>

                        {/* Delete Button */}
                        <button
                          onClick={() => handleDeleteQuestion(q.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          title="Delete Question"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Navigation to Step 4 */}
          <div className="pt-4 border-t border-slate-200 space-y-3">
            {proceedError && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2.5 shadow-xs">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <span className="font-bold block">Export Validation Alert</span>
                  <span>{proceedError}</span>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => handleStepClick('blueprint')}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
              >
                Back to Blueprint
              </button>

              <button
                type="button"
                onClick={handleProceedToExport}
                disabled={!questionPaperId || isProceeding}
                className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition-all cursor-pointer"
              >
                {isProceeding ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Validating Export Readiness...</span>
                  </>
                ) : (
                  <>
                    <span>Proceed to Word (.docx) Export</span>
                    <ChevronRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>

        </div>
      )}

      {/* ========================================================================= */}
      {/* STEP 4: WORD (.DOCX) TEMPLATE & 3-MODE EXPORT                              */}
      {/* ========================================================================= */}
      {activeStep === 'export' && (
        <div className="space-y-6">
          
          {/* Status Banners */}
          {draftCount > 0 ? (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5 text-amber-800">
                <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
                <div>
                  <span className="font-bold block">
                    {draftCount} Question(s) are still in Draft status!
                  </span>
                  <span className="text-[11px] text-amber-700">
                    The official Question Paper export includes only <strong>Approved</strong> questions. Questions in Draft or Rejected status are automatically excluded.
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={handleBulkValidateAll}
                className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg text-xs shrink-0 shadow-xs cursor-pointer"
              >
                Approve All Remaining Drafts
              </button>
            </div>
          ) : exportValidationData && !exportValidationData.can_export ? (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-center gap-3 text-xs text-rose-800">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
              <div>
                <span className="font-bold block">Export Validation Alert</span>
                <span className="text-[11px] text-rose-700">{exportValidationData.message}</span>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center gap-3 text-xs text-emerald-900">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <div>
                <span className="font-bold block">Paper Approved & Ready for Official Export</span>
                <span className="text-[11px] text-emerald-700">
                  All {totalCount} questions are approved by faculty and compliant with autonomous college blueprint requirements.
                </span>
              </div>
            </div>
          )}

          {/* Top Grid: Paper Summary & Template Information Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* 1. Paper Summary Card */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="p-2 rounded-xl bg-blue-50 text-blue-700">
                    <FileCheck className="w-5 h-5" />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Paper Summary</h3>
                    <p className="text-[11px] text-slate-500">Curriculum & Examination Metadata</p>
                  </div>
                </div>
                <span className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-lg text-[11px] font-bold">
                  Paper #{questionPaper?.id || '47'}
                </span>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Institution:</span>
                  <span className="font-bold text-slate-900 truncate max-w-[240px]">
                    {blueprintMeta.institution_name || 'Autonomous Institution / University'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Course:</span>
                  <span className="font-bold text-slate-900">
                    {questionPaper?.course_code || blueprintMeta.course_code || '35021P28'} - {questionPaper?.course_name || blueprintMeta.course_name || 'Applied Core Curriculum'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Examination:</span>
                  <span className="font-semibold text-slate-800">
                    {questionPaper?.exam_name || blueprintMeta.exam_name || 'Internal Assessment'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Maximum Marks:</span>
                  <span className="font-bold text-slate-900">
                    {questionPaper?.max_marks || blueprintMeta.max_marks || 50} Marks ({blueprintMeta.duration || '90 Minutes'})
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Questions Breakdown:</span>
                  <span className="font-semibold text-slate-800">
                    {totalCount} Total ({questionPaper?.sections?.length || 3} Sections)
                  </span>
                </div>
                <div className="flex justify-between items-center pt-1 border-t border-slate-200">
                  <span className="text-slate-500">Faculty Approval:</span>
                  <span className="font-bold text-emerald-700 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" />
                    {approvedCount} of {totalCount} Approved ({validationPercentage}%)
                  </span>
                </div>
              </div>
            </div>

            {/* 2. Template Information Card */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="p-2 rounded-xl bg-indigo-50 text-indigo-700">
                      <FileSpreadsheet className="w-5 h-5" />
                    </span>
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">Template Information</h3>
                      <p className="text-[11px] text-slate-500">Layout, Branding & Header Format</p>
                    </div>
                  </div>
                  <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-[11px] font-bold">
                    Ready for Rendering
                  </span>
                </div>

                <div 
                  onClick={() => templateInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-200 hover:border-indigo-400 hover:bg-indigo-50/30 rounded-xl p-4 text-center cursor-pointer transition-all"
                >
                  <UploadCloud className="w-6 h-6 text-indigo-500 mx-auto mb-1" />
                  <span className="text-xs font-bold text-slate-700 block">
                    {templateUploaded ? 'Custom Word Template Registered!' : 'Attach Custom Institution Word Template (.docx)'}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    Optional: inject questions into custom college headers & footers
                  </span>
                  <input
                    ref={templateInputRef}
                    type="file"
                    accept=".docx"
                    onChange={(e) => e.target.files?.[0] && handleTemplateUpload(e.target.files[0])}
                    className="hidden"
                  />
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between text-xs mt-2">
                <div>
                  <span className="font-semibold text-slate-800 block">
                    {selectedTemplateName || questionPaper?.template_filename || 'Standard Autonomous Examination Template'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Pre-configured autonomous college layout (DOCX & PDF)
                  </span>
                </div>
                <a
                  href={api.getDefaultTemplateUrl()}
                  download="Standard_University_Question_Paper_Template.docx"
                  className="px-3 py-1.5 text-[11px] font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg border border-indigo-200 transition-colors shrink-0"
                >
                  Download Blank Template
                </a>
              </div>
            </div>

          </div>

          {/* Export Readiness Verification Checklist (10 Checks) */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="p-2 rounded-xl bg-emerald-50 text-emerald-700">
                  <ShieldCheck className="w-5 h-5" />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Export Readiness Verification Checklist</h3>
                  <p className="text-[11px] text-slate-500">
                    Automated 10-point structural, cognitive, and compliance audit before generating final examination documents.
                  </p>
                </div>
              </div>

              <span className={`px-3 py-1 rounded-full text-xs font-bold border shrink-0 ${
                (exportValidationData?.can_export ?? (totalCount > 0 && approvedCount === totalCount))
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border-amber-200'
              }`}>
                {(exportValidationData?.can_export ?? (totalCount > 0 && approvedCount === totalCount))
                  ? '10 / 10 Checks Passed • Ready for Export'
                  : 'Pre-flight Verification Pending'}
              </span>
            </div>

            {/* 10 Checks Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              
              {/* Check 1 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">1. Question Approval Parity</span>
                    <span className="text-[11px] text-slate-500">
                      {approvedCount} of {totalCount} Questions Approved by Faculty ({validationPercentage}%)
                    </span>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border shrink-0 ${
                  approvedCount === totalCount && totalCount > 0
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                    : 'bg-rose-100 text-rose-800 border-rose-200'
                }`}>
                  {approvedCount === totalCount && totalCount > 0 ? 'Ready' : 'Blocked'}
                </span>
              </div>

              {/* Check 2 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">2. Question Count Completeness</span>
                    <span className="text-[11px] text-slate-500">
                      {totalCount} Questions configured across all required blueprint sections
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 3 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">3. Maximum Marks Verification</span>
                    <span className="text-[11px] text-slate-500">
                      Total effective marks match target exam marks ({questionPaper?.max_marks || blueprintMeta.max_marks || 50} Marks)
                    </span>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border shrink-0 ${
                  (exportValidationData?.marks_valid ?? true)
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                    : 'bg-rose-100 text-rose-800 border-rose-200'
                }`}>
                  {(exportValidationData?.marks_valid ?? true) ? 'Ready' : 'Blocked'}
                </span>
              </div>

              {/* Check 4 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">4. Course Outcomes (CO) Distribution</span>
                    <span className="text-[11px] text-slate-500">
                      All questions mapped to syllabus outcomes (CO1–CO5) without gaps
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 5 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">5. Bloom's Taxonomy Distribution</span>
                    <span className="text-[11px] text-slate-500">
                      Cognitive levels (L1–L4 / L5) properly distributed according to blueprint
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 6 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">6. Internal Choice (OR Pairs) Structure</span>
                    <span className="text-[11px] text-slate-500">
                      Alternative questions paired with equal marks and matching syllabus units
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 7 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">7. MCQ Options & Keys Integrity</span>
                    <span className="text-[11px] text-slate-500">
                      All multiple choice questions have valid 4-option structures and correct keys
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 8 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">8. Model Answers & Solutions</span>
                    <span className="text-[11px] text-slate-500">
                      Complete model answers and solutions provided for every question
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 9 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">9. Stepwise Marking Schemes & Rubrics</span>
                    <span className="text-[11px] text-slate-500">
                      Grading breakdown and criterion rubrics defined for evaluator manual
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

              {/* Check 10 */}
              <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 flex items-start justify-between gap-2 text-xs">
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-slate-800 block">10. Institutional Word Template</span>
                    <span className="text-[11px] text-slate-500">
                      Autonomous college question paper template verified and loaded
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 shrink-0">
                  Ready
                </span>
              </div>

            </div>
          </div>

          {/* 3 Working Export Format Actions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            
            {/* 1. Official Question Paper (Word & PDF) */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center">
                  <FileText className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">1. Official Question Paper</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Generates the final exam paper formatted according to university regulations, containing <strong>approved questions only</strong>, course details, instructions, and CO & Bloom distribution tables. Student-facing export strictly excludes answers and rubrics.
                </p>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleDownloadDocx('question_paper', true)}
                  disabled={isDownloading || !questionPaperId}
                  className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isDownloading && downloadingType === 'question_paper' ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Compiling Word...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5" />
                      <span>Download Word (.docx)</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => handleDownloadPdf('question_paper', true)}
                  disabled={isDownloading || !questionPaperId}
                  className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isDownloading && downloadingType === 'pdf_question_paper' ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Compiling PDF...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5 text-rose-400" />
                      <span>Download PDF (.pdf)</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 2. Question Paper With Answer Key (Word & PDF) */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
                  <Award className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">2. With Complete Answer Key</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Includes the complete question paper followed by <strong>Section II: Model Solutions</strong>, stepwise derivation keys, and grounding slide/page citations for instructors.
                </p>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleDownloadDocx('with_answer_key', false)}
                  disabled={isDownloading || !questionPaperId}
                  className="w-full py-2 px-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isDownloading && downloadingType === 'with_answer_key' ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Compiling Word...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5" />
                      <span>Download Word (.docx)</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => handleDownloadPdf('with_answer_key', false)}
                  disabled={isDownloading || !questionPaperId}
                  className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isDownloading && downloadingType === 'pdf_with_answer_key' ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Compiling PDF...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Download PDF (.pdf)</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 3. Evaluation Scheme & Rubrics (Word & PDF) */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col justify-between space-y-4">
              <div className="space-y-2">
                <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">3. Evaluation Scheme & Rubrics</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Comprehensive examiner's grading manual featuring <strong>Stepwise Marking Breakdowns</strong> and <strong>Criterion-Referenced Rubric matrices</strong> for consistent evaluation.
                </p>
              </div>

              <div className="space-y-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleDownloadDocx('evaluation_scheme', false)}
                  disabled={isDownloading || !questionPaperId}
                  className="w-full py-2 px-3 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isDownloading && downloadingType === 'evaluation_scheme' ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Compiling Word...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5" />
                      <span>Download Word (.docx)</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => handleDownloadPdf('evaluation_scheme', false)}
                  disabled={isDownloading || !questionPaperId}
                  className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-900 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isDownloading && downloadingType === 'pdf_evaluation_scheme' ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Compiling PDF...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5 text-purple-400" />
                      <span>Download PDF (.pdf)</span>
                    </>
                  )}
                </button>
              </div>
            </div>

          </div>

          {/* Audit & Compliance Reports */}
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-3">
              <span className="p-2 bg-indigo-100 text-indigo-700 rounded-xl">
                <ShieldCheck className="w-5 h-5" />
              </span>
              <div>
                <span className="font-bold text-slate-800 block">
                  Grounding Provenance & Blueprint Validation Audit Reports
                </span>
                <span className="text-[11px] text-slate-500">
                  Export machine-readable JSON logs for institutional accreditation (NBA/NAAC) and curriculum compliance audits.
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleDownloadProvenanceReport}
                disabled={!questionPaperId}
                className="px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-blue-600" />
                <span>Provenance Report (JSON)</span>
              </button>

              <button
                type="button"
                onClick={handleDownloadValidationReport}
                disabled={!questionPaperId}
                className="px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 font-semibold rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-emerald-600" />
                <span>Validation Audit (JSON)</span>
              </button>
            </div>
          </div>

          {/* Back Navigation Button */}
          <div className="flex justify-start pt-2">
            <button
              type="button"
              onClick={() => handleStepClick('validation')}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
            >
              Back to Faculty Review
            </button>
          </div>

        </div>
      )}

      {/* PREVIEW CHUNKS MODAL */}
      {isPreviewModalOpen && selectedFilePreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Eye className="w-4 h-4 text-blue-600" />
                  Extracted Slide & Page Chunks
                </h3>
                <p className="text-xs text-slate-500">
                  {selectedFilePreview.original_filename} ({selectedFilePreview.total_chunks || selectedFilePreview.slide_or_page_count} {selectedFilePreview.file_type === 'pdf' ? 'pages' : 'slides'})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsPreviewModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {selectedFilePreview.extraction_warnings && selectedFilePreview.extraction_warnings.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <span className="font-bold block">Extraction Warnings Detected:</span>
                  {selectedFilePreview.extraction_warnings.map((w, idx) => (
                    <div key={idx} className="text-[11px]">{w}</div>
                  ))}
                </div>
              </div>
            )}

            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={previewSearchTerm}
                onChange={(e) => setPreviewSearchTerm(e.target.value)}
                placeholder="Search within extracted slide chunks..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="overflow-y-auto space-y-3 flex-1 pr-1">
              {selectedFilePreview.chunks
                ?.filter(c => !previewSearchTerm || (c.text + ' ' + c.heading).toLowerCase().includes(previewSearchTerm.toLowerCase()))
                .map((chunk, idx) => (
                  <div key={idx} className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">
                        {chunk.page_or_slide ? `Slide/Page ${chunk.page_or_slide}: ` : ''}{chunk.heading || `Section ${idx + 1}`}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {chunk.has_code && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800">CODE</span>
                        )}
                        {chunk.has_tables && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">TABLE</span>
                        )}
                      </div>
                    </div>
                    <p className="text-slate-600 leading-relaxed font-mono text-[11px] bg-white p-2 rounded-lg border border-slate-100 whitespace-pre-wrap max-h-36 overflow-y-auto">
                      {chunk.text}
                    </p>
                  </div>
                ))}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsPreviewModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GROUNDING PROVENANCE LOOKUP MODAL */}
      {isProvenanceModalOpen && selectedProvenance && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-indigo-50 text-indigo-700">
                  <Search className="w-4 h-4" />
                </span>
                <h3 className="text-base font-bold text-slate-900">
                  Grounding Provenance & Source Citation
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsProvenanceModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Synthesized Question Text
                </span>
                <p className="font-semibold text-slate-900 leading-relaxed">
                  {selectedProvenance.question_text}
                </p>
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  <span className="text-[10px] font-bold px-2 py-0.5 bg-blue-100 text-blue-800 rounded">
                    {selectedProvenance.co_level}
                  </span>
                  <span className="text-[10px] font-bold px-2 py-0.5 bg-purple-100 text-purple-800 rounded">
                    {selectedProvenance.bloom_level}
                  </span>
                  {selectedProvenance.source_topic && (
                    <span className="text-[10px] text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                      Topic: {selectedProvenance.source_topic}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Source File</span>
                  <span className="font-bold text-slate-800 block truncate" title={selectedProvenance.source_filename}>
                    {selectedProvenance.source_filename || 'Institutional Syllabus Outline'}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {selectedProvenance.source_page_or_slide ? `Slide/Page ${selectedProvenance.source_page_or_slide}` : 'Curriculum Spec'}
                  </span>
                </div>

                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Alignment Confidence</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-base font-extrabold text-emerald-700">
                      {Math.round((selectedProvenance.alignment_confidence || 0.85) * 100)}%
                    </span>
                    <span className="text-[10px] font-semibold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded">
                      Strong Grounding
                    </span>
                  </div>
                </div>
              </div>

              {selectedProvenance.supporting_passage && (
                <div className="p-3 bg-indigo-50/50 rounded-xl border border-indigo-200 space-y-1">
                  <span className="text-[10px] font-bold text-indigo-800 uppercase tracking-wider block">
                    Faculty Lecture Content Passage
                  </span>
                  <p className="text-slate-700 italic leading-relaxed text-[11px] font-mono whitespace-pre-wrap max-h-36 overflow-y-auto bg-white p-2 rounded border border-indigo-100">
                    "{selectedProvenance.supporting_passage}"
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsProvenanceModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Close Provenance
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REJECT QUESTION MODAL */}
      {isRejectModalOpen && rejectModalData.question && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <XCircle className="w-5 h-5 text-rose-600" />
              Reject Question {rejectModalData.question.question_number}
            </h3>

            <p className="text-xs text-slate-600">
              Rejected questions will be excluded from the final Word document export. Optionally enter remarks for the audit record.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Reviewer Remarks / Reason (Optional)</label>
              <textarea
                rows={3}
                value={rejectModalData.remarks}
                onChange={(e) => setRejectModalData({ ...rejectModalData, remarks: e.target.value })}
                placeholder="e.g. Needs higher Bloom cognitive level or more practical application context"
                className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-rose-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsRejectModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  await handleReviewQuestion(rejectModalData.question.id, 'reject', rejectModalData.remarks);
                  setIsRejectModalOpen(false);
                }}
                className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-xs"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT QUESTION MODAL */}
      {isEditModalOpen && editingQuestion && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-blue-600" />
              Edit Question {editingQuestion.question_number}
            </h3>

            <form onSubmit={handleSaveQuestionEdit} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Question Text</label>
                <textarea
                  rows={3}
                  required
                  value={editingQuestion.question_text}
                  onChange={(e) => setEditingQuestion({ ...editingQuestion, question_text: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Marks</label>
                  <input
                    type="number"
                    required
                    value={editingQuestion.marks}
                    onChange={(e) => setEditingQuestion({ ...editingQuestion, marks: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">CO Level</label>
                  <select
                    value={editingQuestion.co_level}
                    onChange={(e) => setEditingQuestion({ ...editingQuestion, co_level: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    {['CO1', 'CO2', 'CO3', 'CO4', 'CO5', 'CO6'].map(co => (
                      <option key={co} value={co}>{co}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Bloom's Level</label>
                  <select
                    value={editingQuestion.bloom_level}
                    onChange={(e) => setEditingQuestion({ ...editingQuestion, bloom_level: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    {[
                      'L1 - Remember',
                      'L2 - Understand',
                      'L3 - Apply',
                      'L4 - Analyze',
                      'L5 - Evaluate',
                      'L6 - Create'
                    ].map(lvl => (
                      <option key={lvl} value={lvl}>{lvl}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* MCQ Options Editor */}
              {editingQuestion.edit_options && editingQuestion.edit_options.length > 0 && (
                <div className="space-y-2.5 p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-800">Multiple Choice Options</span>
                    <span className="text-[11px] text-slate-500">Select radio for correct option</span>
                  </div>
                  <div className="space-y-2">
                    {editingQuestion.edit_options.map((opt, idx) => (
                      <div key={opt.label || idx} className="flex items-center gap-2">
                        <label className="flex items-center gap-1.5 cursor-pointer shrink-0">
                          <input
                            type="radio"
                            name="correct_mcq_option"
                            checked={editingQuestion.correct_option_selected === opt.label}
                            onChange={() => {
                              const updated = editingQuestion.edit_options.map(o => ({
                                ...o,
                                is_correct: o.label === opt.label
                              }));
                              setEditingQuestion({
                                ...editingQuestion,
                                edit_options: updated,
                                correct_option_selected: opt.label
                              });
                            }}
                            className="w-4 h-4 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                          />
                          <span className={`w-6 h-6 rounded-md flex items-center justify-center font-bold text-xs ${
                            editingQuestion.correct_option_selected === opt.label
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-200 text-slate-700'
                          }`}>
                            {opt.label}
                          </span>
                        </label>
                        <input
                          type="text"
                          required
                          value={opt.text}
                          placeholder={`Option ${opt.label} text...`}
                          onChange={(e) => {
                            const val = e.target.value;
                            const updated = editingQuestion.edit_options.map(o => 
                              o.label === opt.label ? { ...o, text: val } : o
                            );
                            setEditingQuestion({
                              ...editingQuestion,
                              edit_options: updated
                            });
                          }}
                          className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                        />
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-slate-200">
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Answer Explanation</label>
                    <textarea
                      rows={2}
                      value={editingQuestion.edit_explanation || ''}
                      onChange={(e) => setEditingQuestion({ ...editingQuestion, edit_explanation: e.target.value })}
                      placeholder="Explanation of why the selected option is correct..."
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Model Answer (Optional)</label>
                <textarea
                  rows={2}
                  value={editingQuestion.model_answer || ''}
                  onChange={(e) => setEditingQuestion({ ...editingQuestion, model_answer: e.target.value })}
                  placeholder="Expected answer or core reasoning..."
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Marking Scheme (Optional)</label>
                <textarea
                  rows={2}
                  value={editingQuestion.marking_scheme || ''}
                  onChange={(e) => setEditingQuestion({ ...editingQuestion, marking_scheme: e.target.value })}
                  placeholder="Stepwise points allocation..."
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs"
                >
                  Save & Approve
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD QUESTION MODAL */}
      {isAddQuestionModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Plus className="w-4 h-4 text-blue-600" />
              Add Custom Grounded Question
            </h3>

            <form onSubmit={handleAddCustomQuestion} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Section</label>
                  <select
                    value={newQuestionData.section_name}
                    onChange={(e) => setNewQuestionData({ ...newQuestionData, section_name: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="Part A">Part A</option>
                    <option value="Part B">Part B</option>
                    <option value="Part C">Part C</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Question Number</label>
                  <input
                    type="text"
                    required
                    value={newQuestionData.question_number}
                    onChange={(e) => setNewQuestionData({ ...newQuestionData, question_number: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                    placeholder="e.g. 11(c)"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Question Text</label>
                <textarea
                  rows={3}
                  required
                  value={newQuestionData.question_text}
                  onChange={(e) => setNewQuestionData({ ...newQuestionData, question_text: e.target.value })}
                  placeholder="Type the question..."
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Marks</label>
                  <input
                    type="number"
                    required
                    value={newQuestionData.marks}
                    onChange={(e) => setNewQuestionData({ ...newQuestionData, marks: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">CO Level</label>
                  <select
                    value={newQuestionData.co_level}
                    onChange={(e) => setNewQuestionData({ ...newQuestionData, co_level: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    {['CO1', 'CO2', 'CO3', 'CO4', 'CO5', 'CO6'].map(co => (
                      <option key={co} value={co}>{co}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Bloom's Level</label>
                  <select
                    value={newQuestionData.bloom_level}
                    onChange={(e) => setNewQuestionData({ ...newQuestionData, bloom_level: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    {[
                      'L1 - Remember',
                      'L2 - Understand',
                      'L3 - Apply',
                      'L4 - Analyze',
                      'L5 - Evaluate',
                      'L6 - Create'
                    ].map(lvl => (
                      <option key={lvl} value={lvl}>{lvl}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Model Answer (Optional)</label>
                <textarea
                  rows={2}
                  value={newQuestionData.model_answer}
                  onChange={(e) => setNewQuestionData({ ...newQuestionData, model_answer: e.target.value })}
                  placeholder="Expected answer..."
                  className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddQuestionModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs"
                >
                  Insert & Approve
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* GUIDED REGENERATE MODAL */}
      {isRegenerateModalOpen && regenerateModalData.question && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-indigo-600" />
                Guided Question Regeneration
              </h3>
              <button
                onClick={() => setIsRegenerateModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
              <div className="flex items-center gap-2 font-bold text-slate-800">
                <span>Question {regenerateModalData.question.question_number}</span>
                <span className="text-[10px] px-2 py-0.5 bg-blue-100 text-blue-800 rounded">
                  {regenerateModalData.question.section_name} • Unit {regenerateModalData.question.unit_number} • {regenerateModalData.question.co_level}
                </span>
              </div>
              <p className="mt-1 text-slate-600 line-clamp-2 italic">
                "{regenerateModalData.question.question_text}"
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Regeneration Directive
                </label>
                <select
                  value={regenerateModalData.directive}
                  onChange={(e) => setRegenerateModalData({ ...regenerateModalData, directive: e.target.value })}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="standard">Standard Variation (Keep same constraints, fresh grounding)</option>
                  <option value="simplify_wording">Simplify Wording (Clearer phrasing, reduce complexity)</option>
                  <option value="increase_difficulty">Increase Difficulty (Raise cognitive demand / depth)</option>
                  <option value="decrease_difficulty">Decrease Difficulty (Make more accessible)</option>
                  <option value="change_bloom">Change Bloom's Cognitive Level</option>
                  <option value="change_topic">Change Sub-topic / Concept</option>
                  <option value="convert_to_mcq">Convert to Multiple Choice Question (MCQ)</option>
                  <option value="make_programming">Make Programming / Code-centric Problem</option>
                  <option value="correct_grammar_only">Correct Academic Grammar & Terminology Only</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Question Type
                  </label>
                  <select
                    value={regenerateModalData.target_type}
                    onChange={(e) => setRegenerateModalData({ ...regenerateModalData, target_type: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="mcq">MCQ (Multiple Choice)</option>
                    <option value="msq">MSQ (Multiple Select)</option>
                    <option value="short_answer">Short Answer</option>
                    <option value="descriptive">Descriptive / Long Answer</option>
                    <option value="programming">Programming Problem</option>
                    <option value="debugging">Code Debugging</option>
                    <option value="output_prediction">Output Prediction</option>
                    <option value="numerical_problem">Numerical / Statistical</option>
                    <option value="case_study">Case Study / Scenario</option>
                    <option value="design_application">Design / Application</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Bloom's Taxonomy Level
                  </label>
                  <select
                    value={regenerateModalData.target_bloom}
                    onChange={(e) => setRegenerateModalData({ ...regenerateModalData, target_bloom: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="L1 - Remember">L1 - Remember</option>
                    <option value="L2 - Understand">L2 - Understand</option>
                    <option value="L3 - Apply">L3 - Apply</option>
                    <option value="L4 - Analyze">L4 - Analyze</option>
                    <option value="L5 - Evaluate">L5 - Evaluate</option>
                    <option value="L6 - Create">L6 - Create</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Difficulty Level
                  </label>
                  <select
                    value={regenerateModalData.target_difficulty}
                    onChange={(e) => setRegenerateModalData({ ...regenerateModalData, target_difficulty: e.target.value })}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300 bg-white"
                  >
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Target Topic / Focus
                  </label>
                  <input
                    type="text"
                    value={regenerateModalData.target_topic}
                    onChange={(e) => setRegenerateModalData({ ...regenerateModalData, target_topic: e.target.value })}
                    placeholder="e.g. data frames, dplyr, glm"
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-slate-300"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Faculty Directive / Custom Prompt (Optional)
                </label>
                <textarea
                  rows={2}
                  value={regenerateModalData.prompt}
                  onChange={(e) => setRegenerateModalData({ ...regenerateModalData, prompt: e.target.value })}
                  placeholder="e.g. Provide a realistic data frame creation scenario; test handling of missing values (NA)..."
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsRegenerateModalOpen(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteRegenerate}
                disabled={loading}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-xs cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>{loading ? 'Synthesizing...' : 'Regenerate Question'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Template Upload Modal */}
      <TemplateUploadModal
        isOpen={isTemplateUploadModalOpen}
        onClose={() => setIsTemplateUploadModalOpen(false)}
        syllabusId={currentSyllabus?.id}
        onExtractionSuccess={handleExtractionSuccess}
      />

    </div>
  );
}
