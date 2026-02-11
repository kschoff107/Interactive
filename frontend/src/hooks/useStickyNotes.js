import { useCallback } from 'react';

/**
 * Shared hook for sticky note CRUD operations across visualization components.
 *
 * @param {Function} setNodes - ReactFlow setNodes setter
 * @param {Function} onDirty - callback invoked after any mutation (e.g. onNodesDragged or setHasUnsavedChanges)
 * @param {Object} [options]
 * @param {Function} [options.onDelete] - extra callback after a note is deleted (e.g. toast)
 * @param {Function} [options.getPosition] - returns {x, y} for new notes (defaults to center with jitter)
 */
export function useStickyNotes(setNodes, onDirty, options = {}) {
  const handleNoteTextChange = useCallback((noteId, newText) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === noteId ? { ...node, data: { ...node.data, text: newText } } : node
      )
    );
    if (onDirty) onDirty();
  }, [setNodes, onDirty]);

  const handleNoteColorChange = useCallback((noteId, newColor) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === noteId ? { ...node, data: { ...node.data, color: newColor } } : node
      )
    );
    if (onDirty) onDirty();
  }, [setNodes, onDirty]);

  const handleDeleteNote = useCallback((noteId) => {
    setNodes((nds) => nds.filter((node) => node.id !== noteId));
    if (onDirty) onDirty();
    if (options.onDelete) options.onDelete();
  }, [setNodes, onDirty, options.onDelete]);

  const handleAddNote = useCallback(() => {
    const noteId = `note-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    // Use custom position callback or default with jitter so stacked adds don't overlap
    const jitterX = Math.round(Math.random() * 60 - 30);
    const jitterY = Math.round(Math.random() * 60 - 30);
    const position = options.getPosition
      ? options.getPosition()
      : { x: 250 + jitterX, y: 150 + jitterY };
    const newNote = {
      id: noteId,
      type: 'stickyNote',
      position,
      data: {
        id: noteId,
        text: '',
        color: 'yellow',
        onTextChange: handleNoteTextChange,
        onColorChange: handleNoteColorChange,
        onDelete: handleDeleteNote,
      },
    };
    setNodes((nds) => [...nds, newNote]);
    if (onDirty) onDirty();
  }, [setNodes, onDirty, handleNoteTextChange, handleNoteColorChange, handleDeleteNote, options.getPosition]);

  return { handleNoteTextChange, handleNoteColorChange, handleDeleteNote, handleAddNote };
}

/**
 * Restore sticky notes from a saved layout, wiring up the provided handlers.
 *
 * @param {Object|null} savedLayout - saved layout containing nodes array
 * @param {Object} handlers - { onTextChange, onColorChange, onDelete }
 * @returns {Array} array of sticky note node objects
 */
export function restoreStickyNotesFromLayout(savedLayout, handlers) {
  const stickyNotes = [];
  if (savedLayout && savedLayout.nodes) {
    savedLayout.nodes.forEach((savedNode) => {
      if (savedNode.type === 'stickyNote') {
        stickyNotes.push({
          id: savedNode.id,
          type: 'stickyNote',
          position: savedNode.position,
          data: {
            id: savedNode.id,
            text: savedNode.data?.text || '',
            color: savedNode.data?.color || 'yellow',
            onTextChange: handlers.onTextChange,
            onColorChange: handlers.onColorChange,
            onDelete: handlers.onDelete,
          },
        });
      }
    });
  }
  return stickyNotes;
}
