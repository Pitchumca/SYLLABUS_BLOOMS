import React, { useState } from 'react';
import { X, Layers, Check, ArrowRight } from 'lucide-react';
import { api } from '../services/api';
import { useApp } from '../context/AppContext';

export default function MergeModal({ isOpen, onClose, book, allBooks, onMerged }) {
  const { notify } = useApp();
  
  if (!isOpen || !book) return null;

  // Find other books that might be potential duplicates
  const candidateBooks = allBooks.filter(
    b => b.id !== book.id && (
      b.is_duplicate ||
      (b.isbn && book.isbn && b.isbn === book.isbn) ||
      b.title.toLowerCase().includes(book.title.toLowerCase().slice(0, 8))
    )
  );

  const [selectedTargetId, setSelectedTargetId] = useState(book.id);
  const [selectedMergeIds, setSelectedMergeIds] = useState(candidateBooks.map(c => c.id));
  const [mergedFields, setMergedFields] = useState({
    title: book.title,
    authors: book.authors || '',
    edition: book.edition || '',
    publisher: book.publisher || '',
    publication_year: book.publication_year || '',
    isbn: book.isbn || '',
    category: book.category
  });

  const handleMerge = async () => {
    if (selectedMergeIds.length === 0) {
      notify('Please select at least one duplicate record to merge with.', 'error');
      return;
    }

    try {
      await api.mergeBooks(selectedTargetId, selectedMergeIds, mergedFields);
      notify('Records merged successfully', 'success');
      onMerged();
      onClose();
    } catch (err) {
      notify(err.message || 'Failed to merge books', 'error');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-fade-in">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-2xl overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-amber-50/50">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-amber-700">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Merge Duplicate Records</h3>
              <p className="text-[11px] text-slate-500">Combine duplicate bibliographic entries into a single confirmed record</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs">
          {/* Candidate records list */}
          <div>
            <label className="font-semibold text-slate-700 block mb-2">
              Select records to combine with:
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              <div className="p-3 rounded-xl border border-blue-200 bg-blue-50/60 flex items-start gap-2">
                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-200 text-blue-800 shrink-0">
                  Primary
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-slate-900">{book.title}</div>
                  <div className="text-[11px] text-slate-500">{book.authors || 'No authors'} • {book.publisher || 'No publisher'} • {book.isbn || 'No ISBN'}</div>
                </div>
              </div>

              {candidateBooks.map(c => (
                <label 
                  key={c.id} 
                  className={`p-3 rounded-xl border flex items-start gap-2 cursor-pointer transition-colors ${
                    selectedMergeIds.includes(c.id) ? 'border-amber-300 bg-amber-50/60' : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedMergeIds.includes(c.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedMergeIds([...selectedMergeIds, c.id]);
                      } else {
                        setSelectedMergeIds(selectedMergeIds.filter(id => id !== c.id));
                      }
                    }}
                    className="mt-1 rounded text-amber-600"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-900">{c.title}</div>
                    <div className="text-[11px] text-slate-500">{c.authors || 'No authors'} • {c.publisher || 'No publisher'} • {c.isbn || 'No ISBN'}</div>
                  </div>
                </label>
              ))}

              {candidateBooks.length === 0 && (
                <p className="text-slate-400 italic text-center py-2">
                  No other duplicate candidates detected automatically. You can still refine the details below.
                </p>
              )}
            </div>
          </div>

          {/* Form fields for the final merged record */}
          <div className="pt-3 border-t border-slate-200">
            <h4 className="font-semibold text-slate-800 mb-2">Final Merged Record Details</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-[11px] font-medium text-slate-600 block mb-1">Title</label>
                <input
                  type="text"
                  value={mergedFields.title}
                  onChange={(e) => setMergedFields({ ...mergedFields, title: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                />
              </div>
              <div className="col-span-2">
                <label className="text-[11px] font-medium text-slate-600 block mb-1">Author(s)</label>
                <input
                  type="text"
                  value={mergedFields.authors}
                  onChange={(e) => setMergedFields({ ...mergedFields, authors: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-1">Publisher</label>
                <input
                  type="text"
                  value={mergedFields.publisher}
                  onChange={(e) => setMergedFields({ ...mergedFields, publisher: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-slate-600 block mb-1">ISBN</label>
                <input
                  type="text"
                  value={mergedFields.isbn}
                  onChange={(e) => setMergedFields({ ...mergedFields, isbn: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl font-medium"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleMerge}
              className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-semibold shadow-xs flex items-center gap-1.5"
            >
              <Check className="w-4 h-4" />
              <span>Confirm & Merge Records</span>
            </button>
          </div>

        </div>

      </div>
    </div>
  );
}
