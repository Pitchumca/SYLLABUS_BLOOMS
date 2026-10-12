import React, { useState, useRef, useEffect } from 'react';
import { 
  Check, 
  ChevronDown, 
  Search, 
  X, 
  AlertTriangle, 
  Layers, 
  Code, 
  FileText, 
  CheckSquare, 
  Sparkles 
} from 'lucide-react';

export const QUESTION_TYPES = [
  { id: 'mcq', label: 'Multiple Choice (MCQ)', category: 'Objective', blooms: ['L1', 'L2'], desc: 'Single correct choice among options' },
  { id: 'multiple_select', label: 'Multiple Select (MSQ)', category: 'Objective', blooms: ['L2', 'L3'], desc: 'One or more correct options' },
  { id: 'true_false', label: 'True / False with Reason', category: 'Objective', blooms: ['L1', 'L2'], desc: 'Binary choice with brief technical justification' },
  { id: 'fill_in_blank', label: 'Fill in the Blank', category: 'Objective', blooms: ['L1', 'L2'], desc: 'Targeted keyword or missing syntax' },
  { id: 'matching', label: 'Column Matching', category: 'Objective', blooms: ['L1', 'L2'], desc: 'Map concepts or functions to descriptions' },
  { id: 'assertion_reason', label: 'Assertion & Reason', category: 'Objective', blooms: ['L3', 'L4', 'L5'], desc: 'Validate cause-and-effect relationship' },
  
  { id: 'short_answer', label: 'Short Answer (2M)', category: 'Descriptive', blooms: ['L1', 'L2'], desc: 'Brief definitions, principles, or core concepts' },
  { id: 'descriptive', label: 'Descriptive / Long Answer', category: 'Descriptive', blooms: ['L2', 'L3', 'L4'], desc: 'In-depth conceptual elaboration and mechanisms' },
  { id: 'comparative_analysis', label: 'Comparative Analysis', category: 'Descriptive', blooms: ['L3', 'L4', 'L5'], desc: 'Compare and contrast paradigms, trade-offs' },
  { id: 'open_ended_research', label: 'Open-ended Research / Synthesis', category: 'Descriptive', blooms: ['L5', 'L6'], desc: 'Critical discussion on emerging applications' },

  { id: 'programming', label: 'Programming / Coding', category: 'Coding', blooms: ['L3', 'L4', 'L6'], desc: 'Write complete script, algorithm or module' },
  { id: 'debugging', label: 'Code Debugging', category: 'Coding', blooms: ['L3', 'L4'], desc: 'Identify syntax, runtime or logical bugs' },
  { id: 'code_snippet_analysis', label: 'Output Prediction', category: 'Coding', blooms: ['L2', 'L3', 'L4'], desc: 'Trace execution and predict exact output' },
  { id: 'sql_query', label: 'SQL / Query Formulation', category: 'Coding', blooms: ['L3', 'L4'], desc: 'Relational querying, joins, aggregation' },

  { id: 'numerical_problem', label: 'Numerical / Statistical', category: 'Application', blooms: ['L3', 'L4'], desc: 'Formulas, quantitative analysis, distributions' },
  { id: 'derivation', label: 'Theoretical Derivation', category: 'Application', blooms: ['L3', 'L4'], desc: 'Step-by-step mathematical proof or formulation' },
  { id: 'proof', label: 'Formal Proof', category: 'Application', blooms: ['L4', 'L5'], desc: 'Algorithmic correctness or complexity proof' },
  { id: 'case_study', label: 'Case Study / Scenario', category: 'Application', blooms: ['L4', 'L5', 'L6'], desc: 'Contextual enterprise scenario analysis' },
  { id: 'architecture_diagram', label: 'Architecture / Flowchart', category: 'Application', blooms: ['L4', 'L6'], desc: 'System component layout and workflow schematic' },
  { id: 'design_application', label: 'Design / Application', category: 'Application', blooms: ['L5', 'L6'], desc: 'High-level software/system architecture design' },
];

export const BLOOM_COMPATIBILITY_MATRIX = {
  L1: ['mcq', 'fill_in_blank', 'true_false', 'short_answer', 'matching'],
  L2: ['mcq', 'multiple_select', 'short_answer', 'descriptive', 'code_snippet_analysis', 'matching'],
  L3: ['programming', 'numerical_problem', 'debugging', 'sql_query', 'assertion_reason', 'derivation', 'multiple_select'],
  L4: ['programming', 'debugging', 'code_snippet_analysis', 'case_study', 'comparative_analysis', 'sql_query', 'proof', 'architecture_diagram'],
  L5: ['case_study', 'comparative_analysis', 'open_ended_research', 'assertion_reason', 'design_application', 'proof'],
  L6: ['design_application', 'programming', 'architecture_diagram', 'open_ended_research', 'case_study']
};

export default function MultiSelectQuestionTypes({
  selectedTypes = [],
  onChange,
  bloomLevel = null,
  compact = false
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentList = Array.isArray(selectedTypes) ? selectedTypes : (selectedTypes ? [selectedTypes] : []);

  const toggleType = (typeId) => {
    let next;
    if (currentList.includes(typeId)) {
      next = currentList.filter(id => id !== typeId);
      if (next.length === 0) next = ['short_answer']; // Keep at least one
    } else {
      next = [...currentList, typeId];
    }
    onChange(next);
  };

  const filteredTypes = QUESTION_TYPES.filter(t => 
    t.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.desc.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.category.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Check Bloom compatibility if bloomLevel is provided
  const bloomPrefix = bloomLevel ? bloomLevel.split(' ')[0].trim().toUpperCase() : null;
  const compatibleTypesForBloom = bloomPrefix && BLOOM_COMPATIBILITY_MATRIX[bloomPrefix] 
    ? BLOOM_COMPATIBILITY_MATRIX[bloomPrefix] 
    : null;

  const hasIncompatibleType = compatibleTypesForBloom && currentList.some(t => !compatibleTypesForBloom.includes(t));

  return (
    <div className="relative inline-block w-full" ref={containerRef}>
      {/* Selected Types Trigger Pill Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full text-left px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center justify-between gap-1.5 transition-all bg-white ${
          isOpen ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <div className="flex items-center gap-1.5 overflow-hidden flex-wrap max-w-[85%]">
          {currentList.length === 0 ? (
            <span className="text-slate-400 text-xs">Select Question Types...</span>
          ) : currentList.length === 1 ? (
            <span className="truncate text-slate-800">
              {QUESTION_TYPES.find(t => t.id === currentList[0])?.label || currentList[0]}
            </span>
          ) : (
            <div className="flex items-center gap-1 flex-wrap">
              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded font-bold text-[10px]">
                {currentList.length} Types
              </span>
              <span className="text-[11px] text-slate-700 truncate max-w-[140px]">
                {currentList.map(id => QUESTION_TYPES.find(t => t.id === id)?.label.split(' ')[0] || id).join(' + ')}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {hasIncompatibleType && (
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" title="Bloom level mismatch for one or more selected types" />
          )}
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-xl p-2.5 space-y-2 min-w-[280px] max-w-sm animate-in fade-in zoom-in-95 duration-150">
          
          {/* Search bar */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search 20 question types..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
            {searchTerm && (
              <button 
                type="button" 
                onClick={() => setSearchTerm('')} 
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Quick Selection Presets */}
          <div className="flex items-center justify-between text-[10px] text-slate-500 px-1 border-b border-slate-100 pb-1.5">
            <span className="font-semibold">Quick Combinations:</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onChange(['programming', 'descriptive'])}
                className="px-1.5 py-0.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded font-medium"
              >
                Coding + Descriptive
              </button>
              <button
                type="button"
                onClick={() => onChange(['code_snippet_analysis', 'debugging'])}
                className="px-1.5 py-0.5 bg-purple-50 hover:bg-purple-100 text-purple-700 rounded font-medium"
              >
                Output + Debug
              </button>
            </div>
          </div>

          {/* Incompatible Bloom warning if applicable */}
          {hasIncompatibleType && (
            <div className="p-1.5 bg-amber-50 border border-amber-200 rounded-lg text-[10px] text-amber-800 flex items-start gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
              <span>Some selected types may be misaligned with {bloomLevel}. A coherent integrated prompt will be formulated.</span>
            </div>
          )}

          {/* Type list */}
          <div className="max-h-56 overflow-y-auto divide-y divide-slate-100 pr-1">
            {filteredTypes.length === 0 ? (
              <div className="py-4 text-center text-xs text-slate-400">No matching question types found.</div>
            ) : (
              filteredTypes.map((type) => {
                const isSelected = currentList.includes(type.id);
                const isCompatible = !compatibleTypesForBloom || compatibleTypesForBloom.includes(type.id);

                return (
                  <div
                    key={type.id}
                    onClick={() => toggleType(type.id)}
                    className={`py-1.5 px-2 rounded-lg cursor-pointer flex items-start justify-between gap-2 transition-colors ${
                      isSelected ? 'bg-blue-50/70 font-semibold' : 'hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div className={`mt-0.5 w-3.5 h-3.5 rounded border flex items-center justify-center ${
                        isSelected ? 'bg-blue-600 border-blue-600 text-white' : 'border-slate-300 bg-white'
                      }`}>
                        {isSelected && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                      </div>
                      <div>
                        <div className="text-xs text-slate-800 flex items-center gap-1.5">
                          <span>{type.label}</span>
                          <span className="text-[9px] px-1 py-0.2 bg-slate-100 text-slate-500 rounded font-normal">
                            {type.category}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500 leading-tight line-clamp-1">{type.desc}</p>
                      </div>
                    </div>

                    {!isCompatible && (
                      <span className="text-[9px] text-amber-600 font-bold px-1 py-0.5 bg-amber-50 rounded shrink-0" title={`Typical Blooms: ${type.blooms.join(', ')}`}>
                        {type.blooms[0]}+
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Footer stats */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
            <span className="text-slate-500">
              Selected: <strong>{currentList.length}</strong> types
            </span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg text-xs"
            >
              Done
            </button>
          </div>

        </div>
      )}
    </div>
  );
}
