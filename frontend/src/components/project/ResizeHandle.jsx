import React, { useCallback, useEffect, useRef, useState } from 'react';

export default function ResizeHandle({ direction = 'horizontal', onResize }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const lastPositionRef = useRef({ x: 0, y: 0 });

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
    lastPositionRef.current = { x: e.clientX, y: e.clientY };
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
  }, [direction]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      if (direction === 'horizontal') {
        const deltaX = e.clientX - lastPositionRef.current.x;
        onResize(deltaX);
        lastPositionRef.current.x = e.clientX;
      } else {
        const deltaY = e.clientY - lastPositionRef.current.y;
        onResize(deltaY);
        lastPositionRef.current.y = e.clientY;
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging, direction, onResize]);

  const isHorizontal = direction === 'horizontal';
  const active = isHovered || isDragging;

  return (
    <div
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => !isDragging && setIsHovered(false)}
      className={`flex-shrink-0 relative ${
        isHorizontal ? '' : 'border-t border-gray-200 dark:border-gray-700'
      }`}
      style={isHorizontal
        ? { width: 5, cursor: 'col-resize', marginLeft: -2, marginRight: -2, zIndex: 10 }
        : { height: 8, cursor: 'row-resize', zIndex: 10 }
      }
    >
      {/* Highlight overlay on hover/drag */}
      <div
        className={`absolute inset-0 transition-colors duration-150 ${
          active
            ? 'bg-blue-400/40 dark:bg-blue-500/40'
            : ''
        }`}
      />
    </div>
  );
}
