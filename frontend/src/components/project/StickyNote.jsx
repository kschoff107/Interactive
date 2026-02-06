import React, { useState, useRef, useEffect } from 'react';
import { Handle, Position } from 'reactflow';

const COLORS = [
  { name: 'yellow', bg: 'bg-yellow-100 dark:bg-yellow-900', text: 'text-yellow-900 dark:text-yellow-100', border: 'border-yellow-300 dark:border-yellow-700' },
  { name: 'blue', bg: 'bg-blue-100 dark:bg-blue-900', text: 'text-blue-900 dark:text-blue-100', border: 'border-blue-300 dark:border-blue-700' },
  { name: 'green', bg: 'bg-green-100 dark:bg-green-900', text: 'text-green-900 dark:text-green-100', border: 'border-green-300 dark:border-green-700' },
  { name: 'pink', bg: 'bg-pink-100 dark:bg-pink-900', text: 'text-pink-900 dark:text-pink-100', border: 'border-pink-300 dark:border-pink-700' },
];

export default function StickyNote({ data }) {
  const [isEditing, setIsEditing] = useState(false);
  const [text, setText] = useState(data.text || '');
  const [showColorPicker, setShowColorPicker] = useState(false);
  const textareaRef = useRef(null);

  const currentColor = COLORS.find(c => c.name === data.color) || COLORS[0];

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.select();
    }
  }, [isEditing]);

  const handleBlur = () => {
    setIsEditing(false);
    if (data.onTextChange && text !== data.text) {
      data.onTextChange(data.id, text);
    }
  };

  const handleColorChange = (colorName) => {
    setShowColorPicker(false);
    if (data.onColorChange) {
      data.onColorChange(data.id, colorName);
    }
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    if (data.onDelete) {
      data.onDelete(data.id);
    }
  };

  return (
    <div className={`w-64 min-h-32 p-3 rounded-lg shadow-lg border-2 ${currentColor.bg} ${currentColor.border} ${currentColor.text} relative`}>
      {/* Header with color picker and delete */}
      <div className="flex justify-between items-center mb-2">
        <div className="relative">
          <button
            onClick={() => setShowColorPicker(!showColorPicker)}
            className="w-6 h-6 rounded-full border-2 border-gray-400 dark:border-gray-600 hover:scale-110 transition"
            style={{ backgroundColor: currentColor.name === 'yellow' ? '#fef3c7' : currentColor.name === 'blue' ? '#dbeafe' : currentColor.name === 'green' ? '#d1fae5' : '#fce7f3' }}
            title="Change color"
          />
          {showColorPicker && (
            <div className="absolute top-8 left-0 bg-white dark:bg-gray-800 rounded-lg shadow-xl p-2 flex gap-2 z-50 border border-gray-200 dark:border-gray-700">
              {COLORS.map((color) => (
                <button
                  key={color.name}
                  onClick={() => handleColorChange(color.name)}
                  className={`w-8 h-8 rounded-full border-2 ${color.name === data.color ? 'border-gray-800 dark:border-gray-200 scale-110' : 'border-gray-300 dark:border-gray-600'} hover:scale-110 transition`}
                  style={{ backgroundColor: color.name === 'yellow' ? '#fef3c7' : color.name === 'blue' ? '#dbeafe' : color.name === 'green' ? '#d1fae5' : '#fce7f3' }}
                  title={color.name}
                />
              ))}
            </div>
          )}
        </div>
        <button
          onClick={handleDelete}
          className="text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition"
          title="Delete note"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Note text */}
      {isEditing ? (
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setIsEditing(false);
            }
          }}
          className={`w-full min-h-20 p-2 rounded ${currentColor.bg} ${currentColor.text} border border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none`}
          placeholder="Type your note..."
        />
      ) : (
        <div
          onClick={() => setIsEditing(true)}
          className="min-h-20 p-2 cursor-text whitespace-pre-wrap"
        >
          {text || <span className="opacity-50 italic">Click to add note...</span>}
        </div>
      )}

      {/* Hidden handles for ReactFlow (notes don't connect to anything) */}
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}
